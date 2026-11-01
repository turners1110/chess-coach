"""API (spec §26, §29): login and lockout, protected routes, games, review, report card, sync queue."""

import json
from pathlib import Path

import pytest
from argon2 import PasswordHasher
from fastapi.testclient import TestClient

from coach import api, importer

JAN = json.loads((Path(__file__).parent / "fixtures" / "chesscom" / "2025-01.json").read_text())["games"][0]


@pytest.fixture()
def client(db, monkeypatch):
    monkeypatch.setenv("COACH_PASSWORD_HASH", PasswordHasher().hash("correct horse"))
    api._failed.clear()
    return TestClient(api.app)


def auth(client):
    t = client.post("/api/login", json={"password": "correct horse"}).json()["token"]
    return {"Authorization": f"Bearer {t}"}


def test_login_and_protection(client):
    assert client.get("/api/games").status_code == 401
    assert client.post("/api/login", json={"password": "nope"}).status_code == 401
    h = auth(client)
    assert client.get("/api/games", headers=h).status_code == 200
    assert client.get("/api/games", headers={"Authorization": "Bearer forged"}).status_code == 401
    client.post("/api/logout", headers=h)
    assert client.get("/api/games", headers=h).status_code == 401


def test_lockout_after_failed_logins(client):
    for _ in range(5):
        assert client.post("/api/login", json={"password": "x"}).status_code == 401
    assert client.post("/api/login", json={"password": "correct horse"}).status_code == 429


def test_games_and_detail_with_scores(client, db):
    p = importer.ensure_player(db, "turners1110")
    importer.import_game(db, p, JAN)
    gid = db.execute("SELECT id FROM games").fetchone()["id"]
    plies = db.execute("SELECT * FROM plies WHERE game_id = %s ORDER BY ply", (gid,)).fetchall()
    target = next(pl["ply"] for pl in plies if pl["mover_is_me"] and pl["ply"] >= 10)
    for pl in plies:  # synthetic scores: the played move is "best" except one blunder by Sam
        loss = 30.0 if pl["ply"] == target else 0.0
        db.execute("INSERT INTO move_scores (game_id, ply, mover_is_me, best_uci, win_best, win_played, win_loss, first_win_loss, eval_delta, "
                   "final_pass, class, labels, gri, context_tags, best_line, refutation, analysis_version) VALUES (%s, %s, %s, %s, 60, %s, %s, %s, 0, "
                   "'first', %s, '{}', %s, '{}', %s, %s, 't')",
                   (gid, pl["ply"], pl["mover_is_me"], pl["uci"], 60 - loss, loss, loss, "blunder" if loss else "good", loss, [pl["uci"]], [pl["uci"]]))
    db.execute("UPDATE games SET analysis_status = 'done' WHERE id = %s", (gid,))
    db.commit()
    h = auth(client)
    lst = client.get("/api/games", headers=h).json()
    assert len(lst) == 1 and lst[0]["blunders"] == 1 and lst[0]["largest_swing"] == 30
    d = client.get(f"/api/games/{gid}", headers=h).json()
    assert len(d["plies"]) == len(d["scores"]) == len(plies)
    assert d["moments"][0]["kind"] == "largest_swing" and d["moments"][0]["ply"] == target
    assert d["scores"][0]["best_san"] == [plies[0]["san"]]
    assert "pgn" not in d["game"]
    assert client.get("/api/games/999999", headers=h).status_code == 404


def test_reportcard_needs_enough_games(client):
    r = client.get("/api/reportcard?time_class=rapid", headers=auth(client)).json()
    assert r["status"] == "not_enough_games"
    assert client.get("/api/reportcard?time_class=chess960", headers=auth(client)).status_code == 422


def test_sync_is_queued_for_the_worker(client, db):
    client.post("/api/sync?resync=202501", headers=auth(client))
    job = db.execute("SELECT * FROM jobs WHERE kind = 'sync'").fetchone()
    assert job["payload"] == {"resync": ["202501"]} and job["priority"] == 20
