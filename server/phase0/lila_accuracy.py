"""Reference port of Lichess move and game accuracy, used to build Phase 1 golden fixtures.

Sources (read in Phase 0, 2026-10-29):
  lila      modules/analyse/src/main/AccuracyPercent.scala   @ 898ad2cdee0aa803d7959d83868efc00097a648b
  lila      modules/tree/src/main/eval.scala (forceAsCp, legacyInitial = cp 15)
  scalachess core/src/main/scala/eval.scala (WinPercent, Cp.CEILING = 1000) @ a4988192e6531f92c806e1603a87467c729d5db1
  scalalib  lila/src/main/scala/Maths.scala (mean, harmonicMean, weightedMean, standardDeviation) @ 31fc151b
"""

from __future__ import annotations

import math
from typing import Optional, Sequence

CP_CEILING = 1000            # scalachess Eval.Cp.CEILING
WIN_K = -0.00368208          # scalachess WinPercent.winningChances MULTIPLIER
LEGACY_INITIAL_CP = 15       # lila evals.legacyInitial


def win_percent_from_cp(cp: int) -> float:
    cp = max(-CP_CEILING, min(CP_CEILING, cp))
    return 50 + 50 * (2 / (1 + math.exp(WIN_K * cp)) - 1)


def win_percent_from_mate(mate: int) -> float:
    """lila: a mate score counts as +/-CEILING centipawns (about 97.5 / 2.5), not 100 / 0.
    mate > 0: side to move mates; mate <= 0: side to move is mated (Mate(0) = mated)."""
    return win_percent_from_cp(CP_CEILING if mate > 0 else -CP_CEILING)


def move_accuracy(before: float, after: float) -> float:
    """AccuracyPercent.fromWinPercents: Win% of the mover before and after the move."""
    if after >= before:
        return 100.0
    win_diff = before - after
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * win_diff) + -3.166924740191411
    return max(0.0, min(100.0, raw + 1))


def _std(xs: Sequence[float]) -> float:
    m = sum(xs) / len(xs)
    return math.sqrt(sum((x - m) ** 2 for x in xs) / len(xs))


def _sliding(xs: list, n: int) -> list[list]:
    # Scala List.sliding: a list shorter than the window yields one window with everything.
    if len(xs) <= n:
        return [xs] if xs else []
    return [xs[i:i + n] for i in range(len(xs) - n + 1)]


def game_accuracy(start_white: bool, cps: list[Optional[int]]) -> Optional[dict]:
    """AccuracyPercent.gameAccuracy. cps: white-POV centipawns, first element is the
    position before the first move (lila prepends legacyInitial = 15). None = missing eval.
    Mate scores must be passed already converted with forceAsCp (i.e. +/- huge ints)."""
    wps = [None if c is None else win_percent_from_cp(c) for c in cps]
    window_size = max(2, min(8, (len(cps) - 1) // 10))
    n_pad = min(window_size, len(wps)) - 2
    windows = [wps[:window_size]] * max(0, n_pad) + _sliding(wps, window_size)
    weights = []
    for w in windows:
        if any(x is None for x in w):
            weights.append(None)
        else:
            weights.append(max(0.5, min(12.0, _std(w))))
    pairs = _sliding(wps, 2)
    by_color = {True: [], False: []}
    for i, (pair, weight) in enumerate(zip(pairs, weights)):
        if len(pair) < 2:
            continue
        prev, nxt = pair
        white = (i % 2 == 0) == start_white
        if prev is None or nxt is None or weight is None:
            continue
        acc = move_accuracy(prev, nxt) if white else move_accuracy(100 - prev, 100 - nxt)
        by_color[white].append((acc, weight))

    def color_acc(items):
        if not items:
            return None
        tw = sum(w for _, w in items)
        if tw == 0:
            return None
        weighted = sum(a * w for a, w in items) / tw
        harmonic = len(items) / sum(1 / max(1, a) for a, _ in items)
        return (weighted + harmonic) / 2

    white, black = color_acc(by_color[True]), color_acc(by_color[False])
    if white is None or black is None:
        return None
    return {"white": white, "black": black}


def force_as_cp(mate: int) -> int:
    """lila forceAsCp for a mate score (white POV)."""
    return (2**31 - 1) - mate if mate > 0 else (-(2**31)) - mate
