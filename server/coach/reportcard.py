"""Report card (spec §12.10): grades on key parameters per time class. Each parameter shows Sam's value with a
game-level bootstrap interval, his own level (his opponents in the same games), and the goal level (reference
games between players near the goal rating). Grade = progress from his level to the goal level."""

from __future__ import annotations

import random
from dataclasses import dataclass

import chess

from coach.analysis import phase_of
from coach.config import cfg


@dataclass(frozen=True)
class Metric:
    key: str
    label: str
    better: str        # higher | lower
    unit: str
    explain: str


METRICS = [
    Metric("accuracy", "Accuracy", "higher", "%", "Lichess-style game accuracy"),
    Metric("blunders", "Blunders per game", "lower", "", "Moves losing 15+ Win% points, decided positions excluded"),
    Metric("mistakes", "Mistakes per game", "lower", "", "Moves losing 10–15 Win% points"),
    Metric("opening_result", "Position after the opening", "higher", "Win%", "Your Win% after move 7"),
    Metric("opening_loss", "Opening losses", "lower", "pts/game", "Win% points lost per game in the first 20 plies"),
    Metric("middlegame_loss", "Middlegame losses", "lower", "pts/move", "Win% points lost per middlegame move"),
    Metric("endgame_loss", "Endgame losses", "lower", "pts/move", "Win% points lost per endgame move"),
    Metric("conversion", "Converting wins", "higher", "%", "Games won after reaching a winning position"),
    Metric("resilience", "Saving bad positions", "higher", "%", "Games not lost after reaching a losing position"),
    Metric("time_pressure", "Moves in time trouble", "lower", "%", "Moves made with under 10% of the base time or 15 s"),
    Metric("lost_on_time", "Games lost on time", "lower", "%", "Share of games lost on the clock"),
    Metric("fast_blunders", "Blunder rate when moving fast", "lower", "× normal", "Blunder rate on moves under 3 s, relative to other moves"),
]


def side_stats(game: dict, plies: list[dict], scores: list[dict], me: bool) -> dict:
    """Per-game raw counts for one side (me=True: Sam; me=False: his opponent; reference games use both)."""
    rc = cfg()["report_card"]
    c = cfg()["classes"]
    res = game["result"] if me else {"win": "loss", "loss": "win", "draw": "draw"}[game["result"]]
    mine = [(s, p) for s, p in zip(scores, plies) if s["mover_is_me"] == me]
    st = {"games": 1, "accuracy": game["accuracy_me"] if me else game["accuracy_opp"],
          "blunders": 0, "mistakes": 0, "opening_loss": 0.0, "moves": {"opening": 0, "middlegame": 0, "endgame": 0},
          "loss": {"opening": 0.0, "middlegame": 0.0, "endgame": 0.0}, "tp_moves": 0, "clock_moves": 0,
          "fast_moves": 0, "fast_blunders": 0, "slow_moves": 0, "slow_blunders": 0,
          "winning": False, "won": res == "win", "losing": False, "not_lost": res != "loss",
          "lost_on_time": res == "loss" and "on time" in (game["termination"] or ""), "opening_result": None,
          "total_loss": 0.0, "blunder_loss": 0.0}
    k = rc["win_at_ply"]
    if len(scores) > k:
        w = scores[k]["win_best"]
        st["opening_result"] = w if scores[k]["mover_is_me"] == me else 100 - w
    for s, p in mine:
        sup = "suppressed" in s["labels"]
        ph = phase_of(chess.Board(p["fen_before"]), s["ply"])
        st["moves"][ph] += 1
        if not sup:
            st["loss"][ph] += s["win_loss"]
            st["total_loss"] += s["win_loss"]
            if s["win_loss"] >= c["blunder"]:
                st["blunders"] += 1
                st["blunder_loss"] += s["win_loss"]
            elif s["win_loss"] >= c["mistake"]:
                st["mistakes"] += 1
        if ph == "opening" and not sup:
            st["opening_loss"] += s["win_loss"]
        if s["win_best"] >= rc["conversion_win_min"]:
            st["winning"] = True
        if s["win_best"] <= rc["resilience_win_max"]:
            st["losing"] = True
        if p["clock_ms"] is not None:
            st["clock_moves"] += 1
            tags = s["context_tags"]
            st["tp_moves"] += "time_pressure" in tags
            blunder = not sup and s["win_loss"] >= c["blunder"]
            if "fast_move" in tags:
                st["fast_moves"] += 1
                st["fast_blunders"] += blunder
            else:
                st["slow_moves"] += 1
                st["slow_blunders"] += blunder
    return st


def _ratio(a, b):
    return a / b if b else None


def aggregate(stats: list[dict]) -> dict:
    """Metric values from per-game stats (means of per-game values, or pooled ratios)."""
    n = len(stats)
    if not n:
        return {m.key: None for m in METRICS}
    tot = lambda f: sum(f(s) for s in stats)
    acc = [s["accuracy"] for s in stats if s["accuracy"] is not None]
    opening = [s["opening_result"] for s in stats if s["opening_result"] is not None]
    win_games = [s for s in stats if s["winning"]]
    lose_games = [s for s in stats if s["losing"]]
    fast = _ratio(tot(lambda s: s["fast_blunders"]), tot(lambda s: s["fast_moves"]))
    slow = _ratio(tot(lambda s: s["slow_blunders"]), tot(lambda s: s["slow_moves"]))
    return {
        "accuracy": sum(acc) / len(acc) if acc else None,
        "blunders": tot(lambda s: s["blunders"]) / n,
        "mistakes": tot(lambda s: s["mistakes"]) / n,
        "opening_result": sum(opening) / len(opening) if opening else None,
        "opening_loss": tot(lambda s: s["opening_loss"]) / n,
        "middlegame_loss": _ratio(tot(lambda s: s["loss"]["middlegame"]), tot(lambda s: s["moves"]["middlegame"])),
        "endgame_loss": _ratio(tot(lambda s: s["loss"]["endgame"]), tot(lambda s: s["moves"]["endgame"])),
        "conversion": 100 * sum(s["won"] for s in win_games) / len(win_games) if win_games else None,
        "resilience": 100 * sum(s["not_lost"] for s in lose_games) / len(lose_games) if lose_games else None,
        "time_pressure": _ratio(100 * tot(lambda s: s["tp_moves"]), tot(lambda s: s["clock_moves"])),
        "lost_on_time": 100 * sum(s["lost_on_time"] for s in stats) / n,
        "fast_blunders": fast / slow if fast is not None and slow else None,
        "_n": {"games": n, "winning": len(win_games), "losing": len(lose_games),
               "fast_moves": tot(lambda s: s["fast_moves"])},
    }


def bootstrap(stats: list[dict], seed: int = 1) -> dict:
    b = cfg()["bootstrap"]
    rng = random.Random(seed)
    draws = {m.key: [] for m in METRICS}
    for _ in range(b["n"]):
        sample = [stats[rng.randrange(len(stats))] for _ in stats]
        agg = aggregate(sample)
        for m in METRICS:
            if agg[m.key] is not None:
                draws[m.key].append(agg[m.key])
    lo_q, hi_q = (1 - b["ci"]) / 2, 1 - (1 - b["ci"]) / 2
    out = {}
    for k, xs in draws.items():
        xs.sort()
        out[k] = [xs[int(lo_q * (len(xs) - 1))], xs[int(hi_q * (len(xs) - 1))]] if len(xs) >= 20 else None
    return out


def grade(you: float | None, level: float | None, goal: float | None, better: str) -> tuple[float | None, str | None]:
    """Progress from your level (0) to the goal level (1), and its letter."""
    rc = cfg()["report_card"]
    if None in (you, level, goal):
        return None, None
    gap = goal - level
    if abs(gap) < rc["min_level_gap_rel"] * max(abs(level), abs(goal), 1e-9):
        return None, None
    f = (you - level) / gap
    for letter, cut in zip("ABCD", rc["grade_cuts"]):
        if f >= cut:
            return f, letter
    return f, "F"


def card(you: list[dict], opponents: list[dict], reference: list[dict] | None) -> dict:
    a_you, a_opp = aggregate(you), aggregate(opponents)
    a_ref = aggregate(reference) if reference else None
    ci = bootstrap(you) if len(you) >= 2 else {}
    rows = []
    for m in METRICS:
        f, letter = grade(a_you[m.key], a_opp[m.key], a_ref[m.key] if a_ref else None, m.better)
        rows.append({"key": m.key, "label": m.label, "better": m.better, "unit": m.unit, "explain": m.explain,
                     "you": a_you[m.key], "ci": ci.get(m.key), "your_level": a_opp[m.key],
                     "goal": a_ref[m.key] if a_ref else None, "progress": f, "grade": letter})
    return {"games": len(you), "reference_games": len(reference) if reference else 0, "metrics": rows, "n": a_you.get("_n")}


def hypotheses(stats: list[dict]) -> list[dict]:
    """Sam's own beliefs (spec §12.9, D8), answered from his games."""
    a = aggregate(stats)
    total = sum(x["total_loss"] for x in stats)
    blunder = sum(x["blunder_loss"] for x in stats)
    opening = sum(x["opening_loss"] for x in stats)
    return [
        {"belief": "Blunders cost me the most", "measure": "Share of all Win% points lost that came from blunders",
         "value": 100 * blunder / total if total else None, "unit": "%"},
        {"belief": "I blunder less when I take my time", "measure": "Blunder rate on moves under 3 s, relative to slower moves",
         "value": a["fast_blunders"], "unit": "×", "n": a["_n"]["fast_moves"] if a.get("_n") else 0},
        {"belief": "I'm weak in the openings", "measure": "Share of all Win% points lost in the first 20 plies",
         "value": 100 * opening / total if total else None, "unit": "%"},
    ]


def load(conn, player_id: int, time_class: str) -> dict:
    """Builds the report card for one time class from analyzed games (window from coach.toml [window])."""
    w = cfg()["window"]
    games = conn.execute(
        "SELECT * FROM games WHERE player_id = %s AND source = 'chesscom' AND time_class = %s AND analysis_status = 'done' "
        "AND played_at >= now() - make_interval(days => %s) ORDER BY played_at DESC LIMIT %s",
        (player_id, time_class, w["max_days"], w["games"])).fetchall()
    refs = conn.execute("SELECT * FROM games WHERE source = 'reference' AND time_class = %s AND analysis_status = 'done'",
                        (time_class,)).fetchall()

    def stats_for(gs, both=False):
        you, opp = [], []
        for g in gs:
            plies = conn.execute("SELECT * FROM plies WHERE game_id = %s ORDER BY ply", (g["id"],)).fetchall()
            scores = conn.execute("SELECT * FROM move_scores WHERE game_id = %s ORDER BY ply", (g["id"],)).fetchall()
            if len(scores) != len(plies):
                continue
            you.append(side_stats(g, plies, scores, True))
            opp.append(side_stats(g, plies, scores, False))
        return you + opp if both else (you, opp)

    you, opp = stats_for(games)
    ref = stats_for(refs, both=True)
    out = {"time_class": time_class, "window_games": w["games"], "window_days": w["max_days"], "goal": cfg()["goal"]["target_rating"]}
    if len(you) < w["min_games"]:
        return {**out, "status": "not_enough_games", "games": len(you), "min_games": w["min_games"]}
    return {**out, "status": "ok", **card(you, opp, ref or None), "hypotheses": hypotheses(you),
            "your_rating": round(sum(g["my_rating"] for g in games) / len(games)),
            "opponent_rating": round(sum(g["opp_rating"] for g in games) / len(games))}
