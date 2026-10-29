"""Phase 0 Appendix B8: build a ~500-puzzle pack from the Lichess puzzle CSV (§20.1).

Usage: python puzzle_pack.py --csv lichess_db_puzzle.csv.zst --out pack.csv

Filters (coach.toml [puzzles]): Popularity >= min_pop, NbPlays >= min_plays; Rating within
[glicko] placement_range. Themes: one Lichess theme per §9.1 detector motif, equal shares. Sam's
own motif frequencies need the Phase 2 detectors, so the shares are re-weighted then. Deterministic
reservoir sampling (seeded), one puzzle per id. Spike, not product code.
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import tomllib
from pathlib import Path

import zstandard

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"

# §9.1 detector -> Lichess theme tag (database.lichess.org theme list).
DETECTOR_THEMES = {
    "hanging_piece": "hangingPiece", "fork": "fork", "pin": "pin", "skewer": "skewer",
    "discovered": "discoveredAttack", "back_rank_mate": "backRankMate", "mate_in_5": "mate",
    "removal_of_defender": "capturingDefender", "trapped_piece": "trappedPiece",
    "promotion": "promotion", "intermezzo": "intermezzo", "defensive_resource": "defensiveMove",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    cfg = tomllib.load(open(CONFIG, "rb"))
    p = cfg["puzzles"]
    lo, hi = cfg["glicko"]["placement_range"]
    themes = list(DETECTOR_THEMES.values())
    quota = {t: p["pack_size"] // len(themes) + (1 if i < p["pack_size"] % len(themes) else 0)
             for i, t in enumerate(themes)}
    rng = random.Random(a.seed)
    res = {t: [] for t in themes}
    seen = {t: 0 for t in themes}
    with open(a.csv, "rb") as fh:
        r = csv.DictReader(io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh), encoding="utf-8"))
        fields = r.fieldnames
        for row in r:
            if int(row["Popularity"]) < p["min_pop"] or int(row["NbPlays"]) < p["min_plays"]:
                continue
            if not lo <= int(row["Rating"]) <= hi:
                continue
            tags = row["Themes"].split()
            # Assign to the rarest matching theme so rare motifs get their share.
            match = [t for t in themes if t in tags]
            if not match:
                continue
            t = min(match, key=lambda x: seen[x])
            seen[t] += 1
            k = quota[t] * 4  # oversample so duplicates across themes can't starve a theme
            if len(res[t]) < k:
                res[t].append(row)
            else:
                j = rng.randrange(seen[t])
                if j < k:
                    res[t][j] = row
    pack, ids = [], set()
    for t in themes:
        rows = sorted(res[t], key=lambda x: x["PuzzleId"])
        rng.shuffle(rows)
        n = 0
        for row in rows:
            if n == quota[t]:
                break
            if row["PuzzleId"] in ids:
                continue
            ids.add(row["PuzzleId"])
            pack.append({**row, "PackTheme": t})
            n += 1
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields + ["PackTheme"])
        w.writeheader()
        w.writerows(pack)
    print({"pack": len(pack), "eligible_per_theme": seen, "rating_range": [lo, hi]})


if __name__ == "__main__":
    main()
