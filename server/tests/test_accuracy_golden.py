"""Golden accuracy fixtures from three of Sam's real games (Phase 0, server/phase0/accuracy_golden.py).

Inputs are stored engine evals; expected values come from the lila port. Phase 1's accuracy code must
reproduce them (Phase 1 gate: within 0.5 of lila)."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "phase0"))
from lila_accuracy import game_accuracy  # noqa: E402

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "accuracy_golden.json").read_text())


@pytest.mark.parametrize("game", FIXTURE["games"], ids=lambda g: g["link"].rsplit("/", 1)[-1])
def test_golden_game_accuracy(game):
    assert len(game["cps_for_lila"]) == len(game["uci"]) + 1
    got = game_accuracy(True, game["cps_for_lila"])
    for color in ("white", "black"):
        assert got[color] == pytest.approx(game["expected_accuracy"][color], abs=1e-9)
