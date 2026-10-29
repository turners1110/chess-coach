"""Phase 0 Appendix B9: size the §16.2 fallback opening reference (Lichess dump, players 1400-2000).

Usage: python explorer_fallback_bench.py --dump part.pgn.zst [--max-plies 20] [--tree-games 20000]

Stage 1 streams the (partial) monthly dump and filters games by header: both ratings within
[theory] fallback_rating_min..max and a blitz or rapid speed (Lichess rule: base + 40 * increment). Stage 2 replays the first max-plies of the first tree-games matching games with
python-chess and counts (canonical position, move) entries with W/D/L, to measure throughput and how the
reference grows. A truncated final frame of a partial download is tolerated. Spike, not product code.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import time
import tomllib
from pathlib import Path

import chess
import zstandard

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"
TAG = re.compile(r'^\[(\w+) "(.*)"\]$')
MOVE_NO = re.compile(r"^\d+\.+$")


def speed(tc: str) -> str | None:
    """Lichess speed from TimeControl 'base+inc': estimated duration = base + 40*inc."""
    if tc == "-" or "+" not in tc:
        return None
    base, inc = map(int, tc.split("+"))
    est = base + 40 * inc
    if est < 29:
        return "ultrabullet"
    if est < 180:
        return "bullet"
    if est < 480:
        return "blitz"
    if est < 1500:
        return "rapid"
    return "classical"


def games(stream):
    headers, moves = {}, []
    for line in stream:
        line = line.rstrip("\n")
        if line.startswith("["):
            if moves:
                yield headers, " ".join(moves)
                headers, moves = {}, []
            m = TAG.match(line)
            if m:
                headers[m.group(1)] = m.group(2)
        elif line:
            moves.append(line)
    if moves:
        yield headers, " ".join(moves)


def sans(movetext, max_plies):
    out = []
    for tok in re.sub(r"\{[^}]*\}", " ", movetext).split():
        if MOVE_NO.match(tok) or tok in ("1-0", "0-1", "1/2-1/2", "*"):
            continue
        out.append(tok.rstrip("?!"))
        if len(out) == max_plies:
            break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dump", required=True)
    ap.add_argument("--max-plies", type=int, default=20)
    ap.add_argument("--tree-games", type=int, default=20000)
    a = ap.parse_args()
    t = tomllib.load(open(CONFIG, "rb"))["theory"]
    lo, hi = t["fallback_rating_min"], t["fallback_rating_max"]
    total = matched = 0
    tree = {}
    t0 = time.perf_counter()
    tree_time = 0.0
    tree_n = 0
    growth = []
    with open(a.dump, "rb") as fh:
        text = io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(fh, read_across_frames=True),
                                encoding="utf-8", errors="replace")
        try:
            for h, mt in games(text):
                total += 1
                try:
                    w, b = int(h.get("WhiteElo", 0)), int(h.get("BlackElo", 0))
                except ValueError:
                    continue
                if not (lo <= w <= hi and lo <= b <= hi) or speed(h.get("TimeControl", "-")) not in ("blitz", "rapid"):
                    continue
                matched += 1
                if tree_n < a.tree_games:
                    s = time.perf_counter()
                    res = h.get("Result")
                    board = chess.Board()
                    for san in sans(mt, a.max_plies):
                        try:
                            mv = board.parse_san(san)
                        except ValueError:
                            break
                        key = (board.fen(en_passant="legal").rsplit(" ", 2)[0], mv.uci())
                        e = tree.setdefault(key, [0, 0, 0])
                        e[{"1-0": 0, "1/2-1/2": 1, "0-1": 2}.get(res, 1)] += 1
                        board.push(mv)
                    tree_n += 1
                    tree_time += time.perf_counter() - s
                    if tree_n in (1000, 5000, 10000, 20000, 50000, 100000):
                        growth.append({"games": tree_n, "entries": len(tree),
                                       "entries_ge_50": sum(1 for v in tree.values() if sum(v) >= 50)})
        except (zstandard.ZstdError, EOFError) as ex:  # truncated partial download
            print("stream ended:", type(ex).__name__)
    wall = time.perf_counter() - t0
    filt = wall - tree_time
    print(json.dumps({
        "games_scanned": total, "games_matched": matched, "match_share": round(matched / max(1, total), 4),
        "scan_games_per_s": round(total / max(1e-9, filt), 0),
        "tree_games": tree_n, "tree_games_per_s": round(tree_n / max(1e-9, tree_time), 0),
        "tree_entries": len(tree), "growth": growth, "wall_s": round(wall, 1)}, indent=1))


if __name__ == "__main__":
    main()
