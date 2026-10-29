"""Phase 0 handoff task 5: golden accuracy fixtures from real games.

Usage: python accuracy_golden.py --pgn games.pgn --pick N1,N2,N3 --out server/tests/fixtures/accuracy_golden_1m.json

For each picked game: Stockfish (Threads 1, first_nodes, MultiPV 1, one hash state per game) evaluates the
position before the first move and after every move. Evals are stored white-POV (cp, or mate distance),
and game accuracy is computed with the lila port (lila_accuracy.py). The fixture stores inputs and expected
outputs, so Phase 1 tests can check its own accuracy code without running an engine. The expected values
come from our port of lila, which passes lila's own unit cases; they are not Lichess server output.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import tomllib
from pathlib import Path

import chess
import chess.engine
import chess.pgn

import lila_accuracy as la

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pgn", required=True)
    ap.add_argument("--pick", required=True, help="comma-separated 0-based game indexes in the PGN")
    ap.add_argument("--engine", default=os.environ.get("STOCKFISH", "stockfish"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    cfg = tomllib.load(open(CONFIG, "rb"))
    e = cfg["engine"]
    games = []
    with open(a.pgn) as f:
        while (g := chess.pgn.read_game(f)) is not None:
            games.append(g)
    eng = chess.engine.SimpleEngine.popen_uci(a.engine)
    eng.configure({"Threads": 1, "Hash": e["hash_mb"]})
    out = {"engine": eng.id.get("name"), "engine_sha256": hashlib.sha256(open(a.engine, "rb").read()).hexdigest(),
           "settings": {"nodes": e["first_nodes"], "threads": 1, "hash_mb": e["hash_mb"], "multipv": 1},
           "cpu": platform.processor() or platform.machine(),
           "note": "Expected values from server/phase0/lila_accuracy.py (port of lila@898ad2cd). "
                   "cps_for_lila prepends legacyInitial (+15) and converts mates with forceAsCp.",
           "games": []}
    for idx in map(int, a.pick.split(",")):
        g = games[idx]
        board = g.board()
        key = g.headers.get("Link", str(idx))
        evals = []  # white-POV eval of each position after each move (index 0 = after move 1)
        moves = list(g.mainline_moves())
        for mv in moves:
            board.push(mv)
            if board.is_checkmate():
                # Side to move is mated: white-POV mate 0 for the winner, as lila stores it.
                evals.append({"mate": 0, "winner_white": board.turn == chess.BLACK})
                continue
            info = eng.analyse(board, chess.engine.Limit(nodes=e["first_nodes"]), game=key)
            s = info["score"].white()
            evals.append({"mate": s.mate()} if s.is_mate() else {"cp": s.score()})
        cps = [la.LEGACY_INITIAL_CP]
        for ev in evals:
            if "cp" in ev:
                cps.append(ev["cp"])
            elif ev["mate"] == 0:
                cps.append(la.force_as_cp(1) if ev["winner_white"] else la.force_as_cp(-1))
            else:
                cps.append(la.force_as_cp(ev["mate"]))
        acc = la.game_accuracy(True, cps)
        out["games"].append({"link": key, "white": g.headers.get("White"), "black": g.headers.get("Black"),
                             "result": g.headers.get("Result"), "time_class": g.headers.get("TimeClass"),
                             "uci": [m.uci() for m in moves], "evals_white_pov": evals,
                             "cps_for_lila": cps, "expected_accuracy": acc})
        print(key, len(moves), acc)
    eng.quit()
    Path(a.out).write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
