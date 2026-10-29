"""Phase 0 benchmark of the §8.1 Stockfish pipeline (first, played-move, deep, boundary passes,
plus the §9.2 null-move threat probe) on real games.

Usage: python pipeline_bench.py --pgn games.pgn --me turners1110 --out results.jsonl [--workers N]

All budgets and thresholds come from server/config/coach.toml. This is a benchmark spike,
not product code: no tablebase substitution (counted separately) and no detectors (not built yet).
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing as mp
import os
import platform
import sys
import time
import tomllib
from pathlib import Path

import chess
import chess.engine
import chess.pgn

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"


def load_cfg():
    with open(CONFIG, "rb") as f:
        return tomllib.load(f)


def win_pct(score: chess.engine.PovScore, turn: chess.Color, cfg) -> float:
    """Lichess Win% for the side to move at the root (§8.3); cp clamped; mate -> 100/0."""
    s = score.pov(turn)
    if s.is_mate():
        m = s.mate()
        return 100.0 if m > 0 else 0.0  # mate(-0) means the mover is mated
    cp = max(-cfg["engine"]["cp_clamp"], min(cfg["engine"]["cp_clamp"], s.score()))
    return 50 + 50 * (2 / (1 + math.exp(-cfg["winpct"]["k"] * cp)) - 1)


def classify(win_loss: float, cfg) -> str:
    c = cfg["classes"]
    if win_loss >= c["blunder"]:
        return "blunder"
    if win_loss >= c["mistake"]:
        return "mistake"
    if win_loss >= c["inaccuracy"]:
        return "inaccuracy"
    return "good"


def near_boundary(win_loss: float, gap: float | None, cfg) -> bool:
    m = cfg["engine"]["boundary_margin"]
    c = cfg["classes"]
    bounds = [c["inaccuracy"], c["mistake"], c["blunder"]]
    if any(abs(win_loss - b) <= m for b in bounds):
        return True
    return gap is not None and abs(gap - cfg["labels"]["unique_gap"]) <= m


def search(engine, board, nodes, multipv, root_moves=None, game_key=None):
    t = time.perf_counter()
    infos = engine.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv,
                           root_moves=root_moves, game=game_key)
    return infos, time.perf_counter() - t


def analyse_position(engine, board, played, mover_is_me, cfg, game_key, timings):
    e = cfg["engine"]
    turn = board.turn
    infos, dt = search(engine, board, e["first_nodes"], e["first_multipv"], game_key=game_key)
    timings["first"] += dt
    lines = {i["pv"][0]: win_pct(i["score"], turn, cfg) for i in infos if i.get("pv")}
    top = [i["pv"][0] for i in infos if i.get("pv")]
    win_best = max(lines.values())
    if played in lines:
        win_played = lines[played]
        played_pass = False
    else:
        pinfo, dt = search(engine, board, e["played_nodes"], 1, root_moves=[played], game_key=game_key)
        timings["played"] += dt
        win_played = win_pct(pinfo[0]["score"], turn, cfg)
        played_pass = True
    first_wl = max(0.0, win_best - win_played)
    rec = {"first_win_loss": round(first_wl, 3), "played_pass": played_pass, "top": [m.uci() for m in top],
           "pieces": len(board.piece_map()), "final_pass": "first"}
    final_wl, gap = first_wl, None

    threshold = e["deep_min_win_loss_me"] if mover_is_me else e["deep_min_win_loss_opp"]
    if first_wl >= threshold:
        cand = list(dict.fromkeys(top[: e["deep_top_k"]] + [played]))
        dinfo, dt = search(engine, board, e["deep_nodes"], len(cand), root_moves=cand, game_key=game_key)
        timings["deep"] += dt
        final_wl, gap = _final(dinfo, played, turn, cfg)
        rec["final_pass"] = "deep"
        if near_boundary(final_wl, gap, cfg):
            binfo, dt = search(engine, board, e["boundary_nodes"], len(cand), root_moves=cand, game_key=game_key)
            timings["boundary"] += dt
            final_wl, gap = _final(binfo, played, turn, cfg)
            rec["final_pass"] = "boundary"

    # §9.2 null-move threat probe for Sam's moves (skipped in check / pawn-only endgames).
    if mover_is_me and not board.is_check() and _has_pieces(board):
        nb = board.copy(stack=False)
        nb.push(chess.Move.null())
        if nb.is_valid():
            _, dt = search(engine, nb, cfg["threats"]["null_move_nodes"], 1, game_key=game_key)
            timings["threat"] += dt

    rec["final_win_loss"] = round(final_wl, 3)
    rec["class"] = classify(final_wl, cfg)
    rec["gap"] = None if gap is None else round(gap, 3)
    return rec


def _final(infos, played, turn, cfg):
    wins = {i["pv"][0]: win_pct(i["score"], turn, cfg) for i in infos if i.get("pv")}
    ordered = sorted(wins.values(), reverse=True)
    gap = ordered[0] - ordered[1] if len(ordered) > 1 else None
    return max(0.0, ordered[0] - wins[played]), gap


def _has_pieces(board):
    return any(board.pieces(pt, c) for pt in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
               for c in (chess.WHITE, chess.BLACK))


def analyse_game(args):
    pgn_text, me, engine_path = args
    cfg = load_cfg()
    import io
    game = chess.pgn.read_game(io.StringIO(pgn_text))
    my_color = chess.WHITE if game.headers.get("White", "").lower() == me.lower() else chess.BLACK
    engine = chess.engine.SimpleEngine.popen_uci(engine_path)
    engine.configure({"Threads": cfg["engine"]["threads"], "Hash": cfg["engine"]["hash_mb"]})
    timings = dict(first=0.0, played=0.0, deep=0.0, boundary=0.0, threat=0.0)
    board = game.board()
    moves = []
    t0 = time.perf_counter()
    game_key = game.headers.get("Link") or game.headers.get("Site") or str(id(game))
    for ply, move in enumerate(game.mainline_moves()):
        mover_is_me = board.turn == my_color
        rec = analyse_position(engine, board, move, mover_is_me, cfg, game_key, timings)
        rec.update(ply=ply, fen=board.fen(), uci=move.uci(), mover_is_me=mover_is_me)
        moves.append(rec)
        board.push(move)
    engine.quit()
    return {"link": game_key, "plies": len(moves), "time_class": game.headers.get("TimeClass"),
            "seconds": round(time.perf_counter() - t0, 2),
            "timings": {k: round(v, 2) for k, v in timings.items()}, "moves": moves}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--me", required=True)
    ap.add_argument("--engine", default=os.environ.get("STOCKFISH", "stockfish"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    cfg = load_cfg()
    workers = a.workers or cfg["engine"]["workers"]
    limit = a.limit or cfg["phase0"]["sample_games"]

    texts = []
    with open(a.pgn) as f:
        while len(texts) < limit:
            g = chess.pgn.read_game(f)
            if g is None:
                break
            texts.append(str(g))
    t0 = time.perf_counter()
    with mp.Pool(workers) as pool, open(a.out, "w") as out:
        for res in pool.imap_unordered(analyse_game, [(t, a.me, a.engine) for t in texts]):
            out.write(json.dumps(res) + "\n")
            print(f"{res['link']}: {res['plies']} plies, {res['seconds']} s {res['timings']}", flush=True)
    wall = time.perf_counter() - t0
    print(json.dumps({"games": len(texts), "workers": workers, "wall_s": round(wall, 1),
                      "wall_s_per_game": round(wall / max(1, len(texts)), 1),
                      "cpu": platform.processor() or platform.machine()}))


if __name__ == "__main__":
    sys.exit(main())
