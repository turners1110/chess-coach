"""Analysis (spec §8): determinism gate, stored fields, tablebase substitution, review moments (§12.1).
Engine tests need STOCKFISH (a Stockfish 18 binary) and run with small node budgets."""

import json
import os
from pathlib import Path

import chess
import httpx
import pytest

from coach import analysis, importer, review, tablebase
from coach.config import cfg

FIX = Path(__file__).parent / "fixtures" / "chesscom"
JAN = json.loads((FIX / "2025-01.json").read_text())["games"][0]
needs_engine = pytest.mark.skipif(not os.environ.get("STOCKFISH"), reason="STOCKFISH not set")


@pytest.fixture()
def small_budgets(monkeypatch):
    e = cfg()["engine"]
    for k, v in {"first_nodes": 20_000, "played_nodes": 20_000, "deep_nodes": 60_000, "boundary_nodes": 120_000}.items():
        monkeypatch.setitem(e, k, v)


def load_game(db):
    p = importer.ensure_player(db, "turners1110")
    assert importer.import_game(db, p, JAN) == "new"
    return db.execute("SELECT id FROM games").fetchone()["id"]


def snapshot(db, gid):
    return [tuple(r.values()) for r in db.execute(
        "SELECT ply, best_uci, win_best, win_played, win_loss, first_win_loss, eval_delta, final_pass, class, labels, gap, gri, "
        "context_tags, best_line, refutation FROM move_scores WHERE game_id = %s ORDER BY ply", (gid,))]


@needs_engine
def test_determinism(db, small_budgets):
    gid = load_game(db)
    eng = analysis.Engine()
    try:
        r1 = analysis.analyse_game(db, gid, eng, None)
    finally:
        eng.close()
    first = snapshot(db, gid)
    db.execute("DELETE FROM engine_evals")       # no cache: the second run searches again with a fresh engine
    eng = analysis.Engine()
    try:
        r2 = analysis.analyse_game(db, gid, eng, None)
    finally:
        eng.close()
    assert snapshot(db, gid) == first
    assert r1["accuracy"] == r2["accuracy"]


@needs_engine
def test_stored_fields(db, small_budgets):
    gid = load_game(db)
    eng = analysis.Engine()
    try:
        analysis.analyse_game(db, gid, eng, None)
    finally:
        eng.close()
    g = db.execute("SELECT * FROM games WHERE id = %s", (gid,)).fetchone()
    rows = db.execute("SELECT * FROM move_scores WHERE game_id = %s ORDER BY ply", (gid,)).fetchall()
    plies = db.execute("SELECT * FROM plies WHERE game_id = %s ORDER BY ply", (gid,)).fetchall()
    assert g["analysis_status"] == "done" and 0 <= g["accuracy_me"] <= 100 and 0 <= g["accuracy_opp"] <= 100
    assert len(rows) == len(plies) == g["n_plies"]
    for r, p in zip(rows, plies):
        b = chess.Board(p["fen_before"])
        assert chess.Move.from_uci(r["best_uci"]) in b.legal_moves
        assert r["win_loss"] >= 0 and r["eval_delta"] >= 0
        assert r["class"] in ("good", "inaccuracy", "mistake", "blunder")
        assert r["final_pass"] in ("first", "deep", "boundary", "tablebase")
        assert abs(r["win_loss"] - max(0, r["win_best"] - r["win_played"])) < 1e-3
        if r["final_pass"] == "first":
            assert r["eval_delta"] == 0
        if p["uci"] == r["best_uci"]:
            assert r["win_loss"] == 0
        assert any(t.startswith("move_type:") for t in r["context_tags"])
    deep_threshold = cfg()["engine"]["deep_min_win_loss_me"]
    assert all(r["final_pass"] != "first" for r in rows if r["mover_is_me"] and r["first_win_loss"] >= deep_threshold)


def test_tablebase_substitution(db):
    fen = "8/8/8/8/8/2k5/8/KQ6 w - - 0 1"
    payload = {"category": "win", "dtz": 13, "moves": [{"uci": "b1b2", "category": "loss", "dtz": -12},
                                                       {"uci": "b1c1", "category": "draw", "dtz": 0}]}
    calls = []
    def handler(req):
        calls.append(str(req.url))
        return httpx.Response(200, json=payload)
    tb = tablebase.Tablebase(transport=httpx.MockTransport(handler))
    b = chess.Board(fen)
    s = analysis.score_move(db, eng=None, tb=tb, board=b, fen_norm="k", played=chess.Move.from_uci("b1c1"), mover_is_me=True, game_key=None)
    assert s["final_pass"] == "tablebase" and s["win_best"] == 100 and s["win_played"] == 50 and s["win_loss"] == 50
    analysis.score_move(db, eng=None, tb=tb, board=b, fen_norm="k", played=chess.Move.from_uci("b1b2"), mover_is_me=True, game_key=None)
    assert len(calls) == 1      # second probe served from tb_results


def test_tablebase_failure_falls_back(db):
    tb = tablebase.Tablebase(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    assert tb.probe(db, chess.Board("8/8/8/8/8/2k5/8/KQ6 w - - 0 1"), "x") is None


def row(ply, me, loss, cls=None, labels=(), gri=None):
    return {"ply": ply, "mover_is_me": me, "win_loss": loss, "class": cls or analysis.classify(loss), "labels": list(labels),
            "gri": loss if gri is None else gri}


def test_review_moments():
    scores = [row(0, True, 2), row(1, False, 30), row(2, True, 20), row(3, False, 1), row(4, True, 40, labels=["suppressed"]),
              row(5, False, 12), row(6, True, 6), row(7, False, 0), row(8, True, 11, gri=13.2), row(9, False, 16), row(10, True, 1)]
    m = review.moments(scores)
    assert m[0]["kind"] == "largest_swing" and m[0]["ply"] == 4           # largest objective swing, even when decided
    assert [x["ply"] for x in m if x["kind"] == "important"] == [2, 8]     # next highest GRI, flagged only
    un = [x for x in m if x["kind"] == "unpunished"]
    assert [x["ply"] for x in un] == [1, 5]                                # opponent mistakes Sam's reply did not punish
