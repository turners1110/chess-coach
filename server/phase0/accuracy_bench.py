"""Phase 0 engine-accuracy benchmark (§8.2, Appendix B5).

Takes the per-move output of pipeline_bench.py, samples positions (Sam's moves; half flagged at first pass,
half not, so the error classes are well represented), and compares the pipeline's final class and win_loss
with a reference built from reference_nodes searches:
  A) reference_nodes, MultiPV 1, full width       -> reference best move b*
  B) reference_nodes, one MultiPV search over {b*, pipeline top-3, played}  -> reference win_loss and class
Reports class agreement (overall and re-weighted to the real flagged/unflagged mix), mean |win_loss error|,
and the boundary-recheck rate.

Usage: python accuracy_bench.py --moves results.jsonl --out acc.jsonl [--workers N] [--n 500]
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import random
import statistics
import time
from pathlib import Path

import chess
import chess.engine

from pipeline_bench import classify, load_cfg, win_pct


def reference(args):
    rec, engine_path = args
    cfg = load_cfg()
    e = cfg["engine"]
    eng = chess.engine.SimpleEngine.popen_uci(engine_path)
    eng.configure({"Threads": 1, "Hash": e["hash_mb"]})
    board = chess.Board(rec["fen"])
    played = chess.Move.from_uci(rec["uci"])
    t0 = time.perf_counter()
    a = eng.analyse(board, chess.engine.Limit(nodes=e["reference_nodes"]), multipv=1, game="refA" + rec["fen"])
    best = a[0]["pv"][0]
    cand = list(dict.fromkeys([best, played] + [chess.Move.from_uci(u) for u in rec.get("top", [])]))
    b = eng.analyse(board, chess.engine.Limit(nodes=e["reference_nodes"]), multipv=len(cand), root_moves=cand,
                    game="refB" + rec["fen"])
    eng.quit()
    wins = {i["pv"][0]: win_pct(i["score"], board.turn, cfg) for i in b if i.get("pv")}
    ref_wl = max(0.0, max(wins.values()) - wins[played])
    return {**rec, "ref_win_loss": round(ref_wl, 3), "ref_class": classify(ref_wl, cfg),
            "ref_seconds": round(time.perf_counter() - t0, 1)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--moves", required=True)
    ap.add_argument("--engine", default=os.environ.get("STOCKFISH", "stockfish"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=None)
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cfg = load_cfg()
    n = a.n or cfg["phase0"]["accuracy_positions"]
    workers = a.workers or cfg["engine"]["workers"]

    mine = []
    for line in open(a.moves):
        g = json.loads(line)
        for m in g["moves"]:
            if m["mover_is_me"]:
                mine.append(m)
    thr = cfg["engine"]["deep_min_win_loss_me"]
    flagged = [m for m in mine if m["first_win_loss"] >= thr]
    unflagged = [m for m in mine if m["first_win_loss"] < thr]
    rng = random.Random(a.seed)
    k = min(len(flagged), n // 2)
    sample = rng.sample(flagged, k) + rng.sample(unflagged, min(len(unflagged), n - k))
    share_flagged = len(flagged) / max(1, len(mine))

    done = []
    with mp.Pool(workers) as pool, open(a.out, "w") as out:
        for r in pool.imap_unordered(reference, [(m, a.engine) for m in sample]):
            out.write(json.dumps(r) + "\n")
            done.append(r)

    def agree(rows):
        return sum(r["class"] == r["ref_class"] for r in rows) / max(1, len(rows))

    fl = [r for r in done if r["first_win_loss"] >= thr]
    un = [r for r in done if r["first_win_loss"] < thr]
    deep = [r for r in done if r["final_pass"] in ("deep", "boundary")]
    summary = {
        "positions": len(done), "flagged_in_sample": len(fl), "unflagged_in_sample": len(un),
        "population_share_flagged": round(share_flagged, 3),
        "class_agreement_sample": round(agree(done), 4),
        "class_agreement_flagged": round(agree(fl), 4),
        "class_agreement_unflagged": round(agree(un), 4),
        "class_agreement_population_weighted": round(share_flagged * agree(fl) + (1 - share_flagged) * agree(un), 4),
        "mean_abs_win_loss_error": round(statistics.mean(abs(r["final_win_loss"] - r["ref_win_loss"]) for r in done), 3),
        "mean_abs_win_loss_error_flagged": round(statistics.mean(abs(r["final_win_loss"] - r["ref_win_loss"]) for r in fl), 3) if fl else None,
        "boundary_recheck_rate_of_deep": round(sum(r["final_pass"] == "boundary" for r in deep) / max(1, len(deep)), 3),
        "confusion": {},
    }
    for r in done:
        key = f'{r["class"]}->{r["ref_class"]}'
        summary["confusion"][key] = summary["confusion"].get(key, 0) + 1
    print(json.dumps(summary, indent=1))
    Path(a.out).with_suffix(".summary.json").write_text(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
