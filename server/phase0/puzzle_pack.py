"""Phase 0 (B8): build a 500-puzzle pack from the Lichess puzzle CSV.

Filters from coach.toml [puzzles] (Popularity, NbPlays). Weaknesses are not diagnosed until Phase 3, so this
feasibility pack spreads evenly over the §9.1 motifs and over the Glicko placement range ([glicko]
placement_range). Every puzzle is replayed with python-chess: the first move is the opponent's (Lichess
convention), and the whole line must be legal.

Usage: zstd -dc lichess_db_puzzle.csv.zst | python puzzle_pack.py --out pack.json
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import tomllib
from pathlib import Path

import chess

CFG = tomllib.load(open(Path(__file__).resolve().parents[1] / "config" / "coach.toml", "rb"))
# Lichess theme tags for the §9.1 motifs.
MOTIF_THEMES = {
    "hanging_piece": "hangingPiece", "fork": "fork", "pin": "pin", "skewer": "skewer",
    "discovered": "discoveredAttack", "back_rank_mate": "backRankMate", "mate_in_5": "mateIn2",
    "removal_of_defender": "capturingDefender", "trapped_piece": "trappedPiece", "promotion": "promotion",
    "intermezzo": "intermezzo", "defensive_resource": "defensiveMove", "overload": "deflection",  # Lichess has no overload tag; deflection is closest
}


def legal_line(fen: str, moves: list[str]) -> bool:
    try:
        b = chess.Board(fen)
        for u in moves:
            m = chess.Move.from_uci(u)
            if m not in b.legal_moves:
                return False
            b.push(m)
        return len(moves) >= 2
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    p, g = CFG["puzzles"], CFG["glicko"]
    lo, hi = g["placement_range"]
    per_motif = p["pack_size"] // len(MOTIF_THEMES)
    buckets: dict[str, list[dict]] = {k: [] for k in MOTIF_THEMES}
    rng = random.Random(a.seed)
    total = kept = 0
    for row in csv.DictReader(sys.stdin):
        total += 1
        if int(row["Popularity"]) < p["min_pop"] or int(row["NbPlays"]) < p["min_plays"]:
            continue
        r = int(row["Rating"])
        if not lo <= r <= hi:
            continue
        kept += 1
        themes = row["Themes"].split()
        for motif, theme in MOTIF_THEMES.items():
            if theme in themes:
                lst = buckets[motif]
                # reservoir sample of 20× the needed size per motif, then stratify by rating later
                if len(lst) < per_motif * 20:
                    lst.append(row)
                elif rng.random() < 0.01:
                    lst[rng.randrange(len(lst))] = row
    pack, seen, illegal = [], set(), 0
    for motif, rows in buckets.items():
        rows.sort(key=lambda x: int(x["Rating"]))
        step = max(1, len(rows) // per_motif)
        for row in rows[::step]:
            if len([x for x in pack if x["motif"] == motif]) >= per_motif or row["PuzzleId"] in seen:
                continue
            moves = row["Moves"].split()
            if not legal_line(row["FEN"], moves):
                illegal += 1
                continue
            seen.add(row["PuzzleId"])
            pack.append({"puzzle_id": row["PuzzleId"], "fen": row["FEN"], "moves": moves, "rating": int(row["Rating"]),
                         "rd": int(row["RatingDeviation"]), "popularity": int(row["Popularity"]),
                         "nb_plays": int(row["NbPlays"]), "themes": row["Themes"].split(),
                         "opening_tags": row["OpeningTags"].split(), "motif": motif})
    # top up to pack_size from the largest buckets
    for motif, rows in sorted(buckets.items(), key=lambda kv: -len(kv[1])):
        for row in rows:
            if len(pack) >= p["pack_size"]:
                break
            if row["PuzzleId"] in seen or not legal_line(row["FEN"], row["Moves"].split()):
                continue
            seen.add(row["PuzzleId"])
            pack.append({"puzzle_id": row["PuzzleId"], "fen": row["FEN"], "moves": row["Moves"].split(),
                         "rating": int(row["Rating"]), "rd": int(row["RatingDeviation"]),
                         "popularity": int(row["Popularity"]), "nb_plays": int(row["NbPlays"]),
                         "themes": row["Themes"].split(), "opening_tags": row["OpeningTags"].split(), "motif": motif})
    Path(a.out).write_text(json.dumps(pack, indent=0))
    by_motif = {m: sum(x["motif"] == m for x in pack) for m in MOTIF_THEMES}
    print(json.dumps({"rows": total, "passing_filters_in_range": kept, "pack": len(pack), "illegal_dropped": illegal,
                      "by_motif": by_motif, "rating_min": min(x["rating"] for x in pack),
                      "rating_max": max(x["rating"] for x in pack)}, indent=1))


if __name__ == "__main__":
    main()
