"""Import fixtures (Phase 1 gate): real chess.com archive responses (Feb 2025: rapid, blitz, bullet, daily and
unrated games) served through a mock transport. Checks filters, idempotency, ETag, retries, corrupt PGNs,
clocks and job priorities."""

import copy
import json
from pathlib import Path

import httpx
import pytest

from coach import importer, jobs
from coach.chesscom import Client, FetchFailed

FIX = Path(__file__).parent / "fixtures" / "chesscom"
JAN = json.loads((FIX / "2025-01.json").read_text())
FEB = json.loads((FIX / "2025-02.json").read_text())
U = "https://api.chess.com/pub/player/turners1110"


class Server:
    def __init__(self, months=None):
        self.months = months or {"2025/01": JAN, "2025/02": FEB}
        self.calls, self.fail_next = [], {}

    def __call__(self, req: httpx.Request):
        url = str(req.url)
        self.calls.append((url, req.headers.get("if-none-match"), req.headers.get("user-agent")))
        if self.fail_next.get(url):
            self.fail_next[url] -= 1
            return httpx.Response(429)
        if url == U:
            return httpx.Response(200, json={"player_id": 425089135, "username": "turners1110"})
        if url == U + "/stats":
            return httpx.Response(200, json={"chess_rapid": {"last": {"rating": 1026}}, "chess_blitz": {"last": {"rating": 640}}})
        if url == U + "/games/archives":
            return httpx.Response(200, json={"archives": [f"{U}/games/{m}" for m in self.months]})
        for m, body in self.months.items():
            if url == f"{U}/games/{m}":
                tag = f'W/"{m}-{len(body["games"])}"'
                if req.headers.get("if-none-match") == tag:
                    return httpx.Response(304, headers={"etag": tag})
                return httpx.Response(200, json=body, headers={"etag": tag})
        return httpx.Response(404)


def client(server, sleeps=None):
    return Client(transport=httpx.MockTransport(server), sleep=(sleeps.append if sleeps is not None else lambda s: None))


def test_first_sync_filters_and_counts(db):
    s = Server()
    summary = importer.sync(db, client(s))
    by = dict(db.execute("SELECT time_class, count(*) FROM games GROUP BY 1").fetchall() and
              [(r["time_class"], r["count"]) for r in db.execute("SELECT time_class, count(*) FROM games GROUP BY 1")])
    # Feb 2025: 20 rapid, 4 blitz, 20 bullet, 1 daily rated; 3 unrated bullet skipped. Jan 2025: 1 rapid.
    assert by == {"rapid": 21, "blitz": 4, "bullet": 20, "daily": 1}
    assert summary["games_new"] == 46 and summary["games_failed"] == 0
    assert db.execute("SELECT count(*) AS n FROM games WHERE analysis_status = 'skipped'").fetchone()["n"] >= 1  # daily
    daily = db.execute("SELECT * FROM games WHERE time_class = 'daily'").fetchone()
    assert daily["analysis_status"] == "skipped"
    assert all(ua.startswith("ChessCoach/") for _, _, ua in s.calls)
    assert db.execute("SELECT chesscom_player_id FROM players").fetchone()["chesscom_player_id"] == 425089135
    assert db.execute("SELECT rating FROM ratings_history WHERE time_class = 'rapid'").fetchone()["rating"] == 1026


def test_plies_positions_and_clocks(db):
    importer.sync(db, client(Server()))
    g = db.execute("SELECT * FROM games WHERE time_class = 'rapid' AND time_control = '600' ORDER BY played_at LIMIT 1").fetchone()
    plies = db.execute("SELECT * FROM plies WHERE game_id = %s ORDER BY ply", (g["id"],)).fetchall()
    assert len(plies) == g["n_plies"] > 0
    first_mine = next(p for p in plies if p["mover_is_me"])
    assert first_mine["time_spent_ms"] == 600_000 - first_mine["clock_ms"]  # base - clock + 0 increment
    assert all(p["time_spent_ms"] is not None for p in plies)
    # every ply's position exists exactly once in positions
    n_pos = db.execute("SELECT count(DISTINCT fen_norm_before) AS n FROM plies").fetchone()["n"]
    assert db.execute("SELECT count(*) AS n FROM positions").fetchone()["n"] == n_pos
    assert plies[0]["fen_norm_before"] == "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq -"


def test_second_sync_is_idempotent_and_uses_etag(db):
    s = Server()
    importer.sync(db, client(s))
    n_jobs = db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"]
    s.calls.clear()
    summary = importer.sync(db, client(s))
    month_calls = [c for c in s.calls if "/games/2" in c[0]]
    assert [c[0].rsplit("/", 2)[-2:] for c in month_calls] == [["2025", "02"]]   # past month skipped
    assert month_calls[0][1] == 'W/"2025/02-48"'                               # conditional request
    assert summary == {"months_fetched": 0, "months_unchanged": 1, "games_new": 0, "games_failed": 0, "jobs_enqueued": 0}
    assert db.execute("SELECT count(*) AS n FROM games").fetchone()["n"] == 46
    assert db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == n_jobs


def test_resync_month_refetches_without_duplicates(db):
    s = Server()
    importer.sync(db, client(s))
    importer.sync(db, client(s), resync=["202501"])
    assert db.execute("SELECT count(*) AS n FROM games").fetchone()["n"] == 46


def test_retry_on_429_with_backoff(db):
    s, sleeps = Server(), []
    s.fail_next[f"{U}/games/2025/02"] = 3
    importer.sync(db, client(s, sleeps))
    assert sleeps == [1, 2, 4]
    assert db.execute("SELECT status FROM archives WHERE yyyymm = '202502'").fetchone()["status"] == "done"


def test_gives_up_after_max_tries_and_marks_archive_failed(db):
    s, sleeps = Server(), []
    s.fail_next[f"{U}/games/2025/02"] = 99
    importer.sync(db, client(s, sleeps))
    assert sleeps == [1, 2, 4, 8, 16, 32]           # 6 tries, doubling, capped at 60
    row = db.execute("SELECT status, error FROM archives WHERE yyyymm = '202502'").fetchone()
    assert row["status"] == "failed" and "gave up" in row["error"]
    with pytest.raises(FetchFailed):
        client(s).get(f"{U}/games/2025/02")


def test_corrupt_pgn_is_stored_and_does_not_block(db):
    feb = copy.deepcopy(FEB)
    feb["games"][0]["pgn"] = '[Event "Live Chess"]\n\n1. e4 e5 2. Qh9 *'
    importer.sync(db, client(Server({"2025/01": JAN, "2025/02": feb})))
    bad = db.execute("SELECT * FROM games WHERE parse_status = 'failed'").fetchall()
    assert len(bad) == 1 and bad[0]["analysis_status"] == "skipped" and bad[0]["parse_error"]
    assert db.execute("SELECT count(*) AS n FROM games").fetchone()["n"] == 46


def test_analysis_jobs_recent_first(db):
    importer.sync(db, client(Server()))
    rows = db.execute("SELECT * FROM jobs ORDER BY priority DESC, sort_key DESC").fetchall()
    assert len(rows) == db.execute("SELECT count(*) AS n FROM games WHERE analysis_status = 'pending'").fetchone()["n"]
    assert {r["priority"] for r in rows} == {10}          # fewer than 100 per class: all high priority
    first = jobs.claim(db, ["analyze"])
    newest = db.execute("SELECT id FROM games WHERE analysis_status = 'pending' ORDER BY played_at DESC LIMIT 1").fetchone()["id"]
    assert first["payload"]["game_id"] == newest
