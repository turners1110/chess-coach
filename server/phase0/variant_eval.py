"""Phase 0: re-score the accuracy-benchmark positions under alternative engine budgets.

Reads the reference file written by accuracy_bench.py (one JSON row per position with ref_win_loss/ref_class),
re-runs the §8.1 passes for each position with coach.toml [engine] values overridden on the command line, and
reports class agreement, mean |win_loss error|, boundary-recheck rate and engine seconds per position.
The reference is computed once; this script is cheap by comparison.

Usage: python variant_eval.py --ref acc.jsonl --set first_nodes=300000 --set boundary_nodes=10000000
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import statistics
import time

import chess
import chess.engine

import pipeline_bench as pb


def run(args):
    rec, overrides, engine_path = args
    cfg = pb.load_cfg()
    cfg["engine"].update(overrides)
    eng = chess.engine.SimpleEngine.popen_uci(engine_path)
    eng.configure({"Threads": cfg["engine"]["threads"], "Hash": cfg["engine"]["hash_mb"]})
    timings = dict(first=0.0, played=0.0, deep=0.0, boundary=0.0, threat=0.0)
    board = chess.Board(rec["fen"])
    t0 = time.perf_counter()
    r = pb.analyse_position(eng, board, chess.Move.from_uci(rec["uci"]), True, cfg, "v" + rec["fen"], timings)
    eng.quit()
    timings.pop("threat")  # the threat probe is budget-independent; excluded from per-position cost here
    return {"ref_class": rec["ref_class"], "ref_win_loss": rec["ref_win_loss"], **r,
            "seconds": sum(timings.values()), "wall": time.perf_counter() - t0}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--set", action="append", default=[])
    ap.add_argument("--engine", default=os.environ.get("STOCKFISH", "stockfish"))
    ap.add_argument("--workers", type=int, default=None)
    a = ap.parse_args()
    cfg = pb.load_cfg()
    overrides = {k: int(v) for k, v in (s.split("=") for s in a.set)}
    rows = [json.loads(l) for l in open(a.ref)]
    with mp.Pool(a.workers or cfg["engine"]["workers"]) as pool:
        out = pool.map(run, [(r, overrides, a.engine) for r in rows])
    thr = cfg["engine"]["deep_min_win_loss_me"]
    deep = [o for o in out if o["final_pass"] in ("deep", "boundary")]
    fl = [o for o in out if o["first_win_loss"] >= thr]
    print(json.dumps({
        "overrides": overrides, "positions": len(out),
        "class_agreement": round(sum(o["class"] == o["ref_class"] for o in out) / len(out), 4),
        "class_agreement_flagged": round(sum(o["class"] == o["ref_class"] for o in fl) / max(1, len(fl)), 4),
        "mean_abs_win_loss_error": round(statistics.mean(abs(o["final_win_loss"] - o["ref_win_loss"]) for o in out), 3),
        "boundary_recheck_rate_of_deep": round(sum(o["final_pass"] == "boundary" for o in deep) / max(1, len(deep)), 3),
        "engine_s_per_position": round(statistics.mean(o["seconds"] for o in out), 3),
    }))


if __name__ == "__main__":
    main()
