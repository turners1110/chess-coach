"""Win% golden values (spec v2.2 §8.3). Expected numbers are computed independently here from the Lichess
formula (scalachess eval.scala: 50 + 50 * (2 / (1 + exp(-0.00368208 * cp)) - 1), cp clamped to +/-1000)."""

import math

import pytest

from coach.winpct import win_from_cp, win_from_score


def ref(cp):
    cp = max(-1000, min(1000, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


@pytest.mark.parametrize("cp", [0, 1, -1, 15, 50, -50, 100, -100, 250, 500, -500, 999, 1000, 1001, 1500, -1500, 30000])
def test_win_from_cp_matches_lichess_formula(cp):
    assert win_from_cp(cp) == ref(cp)


def test_known_points():
    assert win_from_cp(0) == 50.0
    assert win_from_cp(100) == pytest.approx(59.1, abs=0.05)
    assert win_from_cp(1000) == pytest.approx(97.54, abs=0.005)
    assert win_from_cp(-1000) == pytest.approx(2.46, abs=0.005)
    assert win_from_cp(5000) == win_from_cp(1000)


def test_mate_scores_like_lila():
    # mate > 0: side to move mates -> +1000 cp; mate <= 0: side to move is mated -> -1000 cp
    assert win_from_score(mate=3) == ref(1000)
    assert win_from_score(mate=-2) == ref(-1000)
    assert win_from_score(mate=0) == ref(-1000)
    assert win_from_score(cp=37) == ref(37)


def test_symmetry():
    for cp in (13, 240, 777):
        assert win_from_cp(cp) + win_from_cp(-cp) == pytest.approx(100, abs=1e-12)
