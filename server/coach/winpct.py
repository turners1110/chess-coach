"""Win% (spec §8.3): the Lichess formula, scalachess core/src/main/scala/eval.scala @ a4988192
(MULTIPLIER -0.00368208, Cp.CEILING 1000). Mates count as +/-ceiling, as in lila."""

from __future__ import annotations

import math

from coach.config import cfg


def win_from_cp(cp: int) -> float:
    c = cfg()
    clamp = c["engine"]["cp_clamp"]
    cp = max(-clamp, min(clamp, cp))
    return 50 + 50 * (2 / (1 + math.exp(-c["winpct"]["k"] * cp)) - 1)


def win_from_score(cp: int | None = None, mate: int | None = None) -> float:
    """Win% for the side to move. mate > 0: the side to move mates; mate <= 0: it is mated."""
    if mate is not None:
        clamp = cfg()["engine"]["cp_clamp"]
        return win_from_cp(clamp if mate > 0 else -clamp)
    return win_from_cp(cp)
