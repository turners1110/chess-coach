"""Phase 0: score a lower-budget pipeline run against the 50M reference already computed by accuracy_bench.py.

Usage: python accuracy_compare.py --ref accuracy.jsonl --moves pipeline_variant.jsonl [--population pipeline.jsonl]

Joins positions on (FEN, played move). Reports class agreement (sample, flagged/unflagged, and re-weighted
to the flagged share of the population run), mean |win_loss error| and the boundary-recheck rate.
"Flagged" means first-pass win_loss >= deep_min_win_loss_me in the *reference sample's* original run,
so both runs are scored on the same positions with the same weights.
"""

from __future__ import annotations

import argparse
import json
import statistics

from pipeline_bench import load_cfg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", required=True)
    ap.add_argument("--moves", required=True)
    ap.add_argument("--population", required=True, help="pipeline run the reference sample was drawn from")
    a = ap.parse_args()
    thr = load_cfg()["engine"]["deep_min_win_loss_me"]
    ref = [json.loads(l) for l in open(a.ref)]
    var = {}
    for line in open(a.moves):
        for m in json.loads(line)["moves"]:
            var[(m["fen"], m["uci"])] = m
    mine = [m for line in open(a.population) for m in json.loads(line)["moves"] if m["mover_is_me"]]
    share = sum(m["first_win_loss"] >= thr for m in mine) / len(mine)
    rows = []
    for r in ref:
        v = var.get((r["fen"], r["uci"]))
        if v:
            rows.append((r, v))

    def agree(rs):
        return sum(v["class"] == r["ref_class"] for r, v in rs) / max(1, len(rs))

    fl = [x for x in rows if x[0]["first_win_loss"] >= thr]
    un = [x for x in rows if x[0]["first_win_loss"] < thr]
    deep = [v for _, v in rows if v["final_pass"] in ("deep", "boundary")]
    print(json.dumps({
        "matched_positions": len(rows), "of_reference": len(ref),
        "class_agreement_sample": round(agree(rows), 4),
        "class_agreement_flagged": round(agree(fl), 4), "class_agreement_unflagged": round(agree(un), 4),
        "class_agreement_population_weighted": round(share * agree(fl) + (1 - share) * agree(un), 4),
        "mean_abs_win_loss_error": round(statistics.mean(abs(v["final_win_loss"] - r["ref_win_loss"]) for r, v in rows), 3),
        "boundary_recheck_rate_of_deep": round(sum(v["final_pass"] == "boundary" for v in deep) / max(1, len(deep)), 3),
    }, indent=1))


if __name__ == "__main__":
    main()
