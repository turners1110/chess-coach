"""Phase 1 gate: game accuracy within 0.5 of lila (spec §27). coach.accuracy against both golden fixture
sets (real games, depth-12 and 1M-node evals) and lila's own unit cases."""

import json
from pathlib import Path

import pytest

from coach import accuracy as acc

FIX = Path(__file__).parent / "fixtures"
GOLD = json.loads((FIX / "accuracy_golden.json").read_text())["games"]
GOLD_1M = json.loads((FIX / "accuracy_golden_1m.json").read_text())["games"]


@pytest.mark.parametrize("g", GOLD, ids=lambda g: g["game"].rsplit("/", 1)[-1])
def test_depth12_fixtures(g):
    got = acc.game_accuracy(True, g["cps_white_pov"])
    for color in ("white", "black"):
        assert abs(got[color] - g["expected"][color]) <= 0.5


@pytest.mark.parametrize("g", GOLD_1M, ids=lambda g: g["link"].rsplit("/", 1)[-1])
def test_1m_fixtures(g):
    got = acc.game_accuracy(True, g["cps_for_lila"])
    for color in ("white", "black"):
        assert abs(got[color] - g["expected_accuracy"][color]) <= 0.5


def test_lila_unit_cases_hold_for_product_module():
    # A subset of lila AccuracyPercentTest.scala (@898ad2cd), same tolerances
    init = acc.LEGACY_INITIAL_CP
    r = acc.game_accuracy(True, [init, 15, 15])
    assert abs(r["white"] - 100) <= 1 and abs(r["black"] - 100) <= 1
    r = acc.game_accuracy(True, [init] + [-50, 15] * 5)
    assert abs(r["white"] - 76) <= 8 and abs(r["black"] - 76) <= 8
