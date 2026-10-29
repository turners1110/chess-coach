"""Port of lila modules/analyse/src/test/AccuracyPercentTest.scala (@898ad2cd), run against
server/phase0/lila_accuracy.py. Same inputs and tolerances as upstream."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase0"))
from lila_accuracy import (LEGACY_INITIAL_CP, force_as_cp, game_accuracy, move_accuracy,  # noqa: E402
                           win_percent_from_cp, win_percent_from_mate)


def compute(cps, start_white=True):
    return game_accuracy(start_white, [LEGACY_INITIAL_CP] + cps)


def close(a, b, d):
    return abs(a - b) <= d


CASES_WHITE = [
    ([15, 15], (100, 1), (100, 1)),
    ([-900, -900], (10, 5), (100, 1)),
    ([15, 900], (100, 1), (10, 5)),
    ([-900, 0], (10, 5), (10, 5)),
    ([15] * 20, (100, 1), (100, 1)),
    ([15] * 20 + [-900], (50, 5), (100, 1)),
    ([15] * 21 + [900], (100, 1), (50, 5)),
    ([-50, 15] * 5, (76, 8), (76, 8)),
    ([-50, 15] * 50, (76, 8), (76, 8)),
    ([-135, 15] * 50, (54, 8), (54, 8)),
    ([-435, 15] * 50, (20, 8), (20, 8)),
]


@pytest.mark.parametrize("cps,white,black", CASES_WHITE)
def test_upstream_white_first(cps, white, black):
    a = compute(cps)
    assert close(a["white"], *white)
    assert close(a["black"], *black)


@pytest.mark.parametrize("cps,black,white", [
    ([15, 15], (100, 1), (100, 1)),
    ([900, 900], (10, 5), (100, 1)),
    ([15, -900], (100, 1), (10, 5)),
    ([900, 0], (10, 5), (10, 5)),
])
def test_upstream_black_first(cps, black, white):
    a = compute(cps, start_white=False)
    assert close(a["black"], *black)
    assert close(a["white"], *white)


def test_empty_and_single():
    assert compute([]) is None
    assert compute([15]) is None
    assert compute([], start_white=False) is None
    assert compute([15], start_white=False) is None


def test_mate_is_ceiling_not_100():
    assert win_percent_from_mate(3) == pytest.approx(win_percent_from_cp(1000))
    assert win_percent_from_mate(0) == pytest.approx(win_percent_from_cp(-1000))
    assert 97.4 < win_percent_from_mate(1) < 97.6
    assert win_percent_from_cp(1500) == win_percent_from_cp(1000)
    assert win_percent_from_cp(force_as_cp(2)) == win_percent_from_cp(1000)


def test_move_accuracy_bounds():
    assert move_accuracy(50, 50) == 100
    assert move_accuracy(50, 60) == 100
    assert move_accuracy(100, 0) == 0
