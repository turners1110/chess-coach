"""Report card (spec §12.10): metric aggregation, grades between your level and the goal level, intervals."""

import pytest

from coach import reportcard as rc


def stats(**kw):
    base = {"games": 1, "accuracy": 80.0, "blunders": 1, "mistakes": 1, "opening_loss": 5.0,
            "moves": {"opening": 10, "middlegame": 20, "endgame": 5}, "loss": {"opening": 5.0, "middlegame": 20.0, "endgame": 10.0},
            "tp_moves": 2, "clock_moves": 35, "fast_moves": 5, "fast_blunders": 1, "slow_moves": 30, "slow_blunders": 0,
            "winning": True, "won": True, "losing": False, "not_lost": True, "lost_on_time": False, "opening_result": 55.0,
            "total_loss": 35.0, "blunder_loss": 20.0}
    base.update(kw)
    return base


def test_aggregate_means_and_pooled_ratios():
    a = rc.aggregate([stats(), stats(accuracy=60.0, blunders=3, winning=True, won=False, fast_blunders=0, slow_blunders=3)])
    assert a["accuracy"] == 70 and a["blunders"] == 2
    assert a["conversion"] == 50
    assert a["middlegame_loss"] == pytest.approx(1.0)
    assert a["fast_blunders"] == pytest.approx((1 / 10) / (3 / 60))


@pytest.mark.parametrize("you,level,goal,better,letter", [
    (75, 70, 80, "higher", "C"),      # halfway from your level to the goal
    (85, 70, 80, "higher", "A"),      # beyond the goal
    (65, 70, 80, "higher", "F"),      # below your own level
    (1.5, 2.0, 1.0, "lower", "C"),    # lower is better: halfway
    (0.9, 2.0, 1.0, "lower", "A"),
    (2.0, 2.0, 1.0, "lower", "D"),    # exactly at your level
])
def test_grades(you, level, goal, better, letter):
    assert rc.grade(you, level, goal, better)[1] == letter


def test_no_grade_when_levels_do_not_differ_or_missing():
    assert rc.grade(70, 70, 70.5, "higher") == (None, None)
    assert rc.grade(70, None, 80, "higher") == (None, None)


def test_card_and_bootstrap_interval():
    you = [stats(accuracy=70.0 + i % 10) for i in range(40)]
    opp = [stats(accuracy=72.0) for _ in range(40)]
    ref = [stats(accuracy=82.0) for _ in range(40)]
    c = rc.card(you, opp, ref)
    acc = next(m for m in c["metrics"] if m["key"] == "accuracy")
    assert acc["you"] == pytest.approx(74.5) and acc["your_level"] == 72 and acc["goal"] == 82
    assert acc["grade"] == "D" and acc["ci"][0] < 74.5 < acc["ci"][1]
    no_ref = rc.card(you, opp, None)
    assert all(m["grade"] is None for m in no_ref["metrics"])


def test_hypotheses():
    h = rc.hypotheses([stats(), stats()])
    assert h[0]["value"] == pytest.approx(100 * 40 / 70)
    assert h[2]["value"] == pytest.approx(100 * 10 / 70)
