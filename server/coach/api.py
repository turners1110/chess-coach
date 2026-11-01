"""HTTP API for the PWA (spec §26, §29). Single-user login (argon2id hash in COACH_PASSWORD_HASH), bearer
tokens stored hashed, CORS for the PWA origin (COACH_ALLOWED_ORIGINS). Syncs are queued as jobs so all
chess.com requests stay serial in the worker (§7.2)."""

from __future__ import annotations

import datetime as dt
import hashlib
import os
import secrets
import time
from collections import deque
from pathlib import Path

import chess
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from coach import db, jobs, reportcard, review
from coach.config import cfg

app = FastAPI(title="Chess Coach API")
origins = [o for o in os.environ.get("COACH_ALLOWED_ORIGINS", "").split(",") if o]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["Authorization", "Content-Type"])
_ph = PasswordHasher()
_failed: deque[float] = deque()


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def user(authorization: str = Header(default="")) -> bool:
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        raise HTTPException(401, "Sign in first")
    with db.connect() as conn:
        row = conn.execute("SELECT 1 FROM auth_sessions WHERE token_hash = %s AND expires_at > now()", (_hash(token),)).fetchone()
    if not row:
        raise HTTPException(401, "Your sign-in has expired")
    return True


class Login(BaseModel):
    password: str


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/login")
def login(body: Login):
    a = cfg()["auth"]
    now = time.time()
    while _failed and _failed[0] < now - a["failed_login_window_min"] * 60:
        _failed.popleft()
    if len(_failed) >= a["max_failed_logins"]:
        raise HTTPException(429, "Too many attempts. Try again in a few minutes.")
    stored = os.environ.get("COACH_PASSWORD_HASH", "")
    if not stored:
        raise HTTPException(503, "No password is set on the server yet (see docs/setup-home-computer.md, step 3).")
    try:
        _ph.verify(stored, body.password)
    except VerificationError:
        _failed.append(now)
        raise HTTPException(401, "Wrong password")
    token = secrets.token_urlsafe(32)
    with db.connect() as conn:
        conn.execute("INSERT INTO auth_sessions (token_hash, expires_at) VALUES (%s, now() + make_interval(days => %s))",
                     (_hash(token), a["session_days"]))
        conn.execute("DELETE FROM auth_sessions WHERE expires_at < now()")
    return {"token": token}


@app.post("/api/logout")
def logout(authorization: str = Header(default=""), _=Depends(user)):
    with db.connect() as conn:
        conn.execute("DELETE FROM auth_sessions WHERE token_hash = %s", (_hash(authorization.removeprefix("Bearer ").strip()),))
    return {"ok": True}


@app.get("/api/status")
def status(_=Depends(user)):
    with db.connect() as conn:
        games = conn.execute("SELECT time_class, analysis_status, count(*) AS n FROM games WHERE source = 'chesscom' GROUP BY 1, 2").fetchall()
        queue = conn.execute("SELECT kind, status, count(*) AS n FROM jobs GROUP BY 1, 2").fetchall()
        sync = conn.execute("SELECT max(last_fetched) AS t FROM archives").fetchone()["t"]
        ratings = conn.execute("SELECT DISTINCT ON (time_class) time_class, rating, date FROM ratings_history ORDER BY time_class, date DESC").fetchall()
    return {"games": games, "jobs": queue, "last_sync": sync, "ratings": ratings, "goal": cfg()["goal"]["target_rating"]}


@app.post("/api/sync")
def sync_now(resync: str | None = None, _=Depends(user)):
    """Queues a sync for the worker. `resync` = yyyymm to re-download one month (§7.2 "Resync month")."""
    key = f"sync:{resync or 'now'}:{dt.datetime.now(dt.timezone.utc):%Y%m%d%H%M}"
    with db.connect() as conn:
        jobs.enqueue(conn, "sync", key, {"resync": [resync] if resync else []}, priority=20)
    return {"queued": True}


@app.get("/api/games")
def games(time_class: str | None = None, limit: int = Query(50, le=200), offset: int = 0, _=Depends(user)):
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT g.id, g.played_at, g.time_class, g.time_control, g.color, g.opponent, g.opp_rating, g.my_rating, g.result, "
            "g.termination, g.opening, g.eco, g.accuracy_me, g.accuracy_opp, g.analysis_status, g.n_plies, "
            "count(*) FILTER (WHERE m.mover_is_me AND m.class = 'blunder' AND NOT 'suppressed' = ANY(m.labels)) AS blunders, "
            "count(*) FILTER (WHERE m.mover_is_me AND m.class = 'mistake' AND NOT 'suppressed' = ANY(m.labels)) AS mistakes, "
            "count(*) FILTER (WHERE m.mover_is_me AND m.class = 'inaccuracy' AND NOT 'suppressed' = ANY(m.labels)) AS inaccuracies, "
            "max(m.win_loss) FILTER (WHERE m.mover_is_me) AS largest_swing "
            "FROM games g LEFT JOIN move_scores m ON m.game_id = g.id "
            "WHERE g.source = 'chesscom' AND g.parse_status = 'ok' AND g.time_class <> 'daily' AND (%s::text IS NULL OR g.time_class = %s) "
            "GROUP BY g.id ORDER BY g.played_at DESC LIMIT %s OFFSET %s", (time_class, time_class, limit, offset)).fetchall()
    return rows


def _san_line(fen: str, ucis: list[str] | None, limit: int = 8) -> list[str]:
    b, out = chess.Board(fen), []
    for u in (ucis or [])[:limit]:
        try:
            m = chess.Move.from_uci(u)
            out.append(b.san(m))
            b.push(m)
        except (ValueError, AssertionError):
            break
    return out


@app.get("/api/games/{gid}")
def game(gid: int, _=Depends(user)):
    with db.connect() as conn:
        g = conn.execute("SELECT * FROM games WHERE id = %s AND source = 'chesscom'", (gid,)).fetchone()
        if not g:
            raise HTTPException(404, "Game not found")
        plies = conn.execute("SELECT ply, san, uci, fen_before, clock_ms, time_spent_ms, mover_is_me FROM plies WHERE game_id = %s ORDER BY ply", (gid,)).fetchall()
        scores = conn.execute("SELECT * FROM move_scores WHERE game_id = %s ORDER BY ply", (gid,)).fetchall()
    for s in scores:
        p = plies[s["ply"]]
        after = chess.Board(p["fen_before"])
        after.push(chess.Move.from_uci(p["uci"]))
        s["best_san"] = _san_line(p["fen_before"], s["best_line"])
        s["refutation_san"] = _san_line(after.fen(), s["refutation"])
        for k in ("created_at", "updated_at"):
            s.pop(k, None)
    g.pop("pgn", None)
    return {"game": g, "plies": plies, "scores": scores, "moments": review.moments(scores) if scores else []}


@app.get("/api/reportcard")
def report(time_class: str = Query(..., pattern="^(blitz|rapid|bullet)$"), _=Depends(user)):
    with db.connect() as conn:
        p = conn.execute("SELECT id FROM players WHERE chesscom_username = %s", (cfg()["player"]["chesscom_username"],)).fetchone()
        if not p:
            return {"time_class": time_class, "status": "not_enough_games", "games": 0, "min_games": cfg()["window"]["min_games"]}
        return reportcard.load(conn, p["id"], time_class)


web = os.environ.get("COACH_WEB_DIST")
if web and Path(web).is_dir():  # serve the built PWA from the same origin (home-computer setup)
    app.mount("/", StaticFiles(directory=web, html=True), name="web")
