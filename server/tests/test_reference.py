"""Reference crawl (spec §12.10): best-first toward the goal rating, keeps only goal-band games at Sam's time controls."""

import copy
import json
from pathlib import Path

import httpx

from coach import reference
from coach.chesscom import Client

FEB = json.loads((Path(__file__).parent / "fixtures" / "chesscom" / "2025-02.json").read_text())


def game(white, wr, black, br, tc="600", tclass="rapid", n=0):
    g = copy.deepcopy(next(x for x in FEB["games"] if x["time_class"] == "rapid" and x["rated"]))
    g["url"] = f"https://www.chess.com/game/live/9{n:05d}"
    g["white"].update(username=white, rating=wr)
    g["black"].update(username=black, rating=br)
    g["time_control"], g["time_class"] = tc, tclass
    return g


def test_crawl_keeps_goal_band_games(db, monkeypatch):
    monkeypatch.setitem(reference.cfg()["reference"], "games_per_class", 2)
    db.execute("INSERT INTO players (chesscom_username) VALUES ('turners1110')")
    pid = db.execute("SELECT id FROM players").fetchone()["id"]
    db.execute("INSERT INTO games (player_id, chesscom_url, time_class, time_control, rated, played_at, color, opp_rating, opponent, result, pgn) "
               "VALUES (%s, 'u0', 'rapid', '600', true, now(), 'w', 1100, 'seed', 'win', '')", (pid,))
    archives = {
        "seed": [game("seed", 1100, "mid", 1300, n=1)],
        "mid": [game("mid", 1300, "near", 1490, n=2), game("near", 1490, "close", 1510, n=3)],
        "near": [game("near", 1495, "close", 1505, n=4), game("near", 1500, "close", 1520, tc="300", tclass="blitz", n=5),
                 game("near", 1500, "far", 1600, n=6), game("near", 1500, "close", 1500, tc="900+10", n=7)],
        "close": [game("close", 1500, "near", 1500, n=8)],
    }
    def handler(req):
        user = str(req.url).split("/player/")[1].split("/")[0]
        return httpx.Response(200, json={"games": archives.get(user, [])})
    out = reference.build(db, Client(transport=httpx.MockTransport(handler), sleep=lambda s: None))
    rows = db.execute("SELECT time_class, my_rating, opp_rating, time_control FROM games WHERE source = 'reference'").fetchall()
    assert out["games"] == {"blitz": 1, "rapid": 2}
    assert all(1450 <= r["my_rating"] <= 1550 and 1450 <= r["opp_rating"] <= 1550 for r in rows)
    assert {r["time_control"] for r in rows} == {"300", "600"}
    assert out["jobs_enqueued"] == 3
