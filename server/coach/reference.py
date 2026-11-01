"""Goal-level reference games for the report card (spec §12.10). A serial, best-first crawl of chess.com:
start from Sam's recent opponents, read players' recent monthly archives, move toward players rated near the
goal, and keep rated games at Sam's time controls where both players are within goal ± band."""

from __future__ import annotations

import datetime as dt
import heapq
import json

from coach import jobs
from coach.chesscom import BASE, Client, FetchFailed
from coach.config import cfg
from coach.importer import ensure_player, import_game
from coach.versions import analysis_version


def build(conn, client: Client) -> dict:
    r, goal = cfg()["reference"], cfg()["goal"]["target_rating"]
    lo, hi = goal - r["band"], goal + r["band"]
    owner = ensure_player(conn, cfg()["player"]["chesscom_username"])
    have = {tc: conn.execute("SELECT count(*) AS n FROM games WHERE source = 'reference' AND time_class = %s", (tc,)).fetchone()["n"]
            for tc in r["time_classes"]}
    seeds = conn.execute("SELECT opponent, max(opp_rating) AS rating FROM games WHERE source = 'chesscom' AND opponent IS NOT NULL "
                         "GROUP BY opponent ORDER BY max(played_at) DESC LIMIT 30").fetchall()
    frontier = [(abs(s["rating"] - goal), s["opponent"].lower()) for s in seeds if s["rating"]]
    # Players from earlier reference games are already near the goal: good seeds for the time classes still missing
    for g in conn.execute("SELECT pgn, my_rating FROM games WHERE source = 'reference' ORDER BY played_at DESC LIMIT 50").fetchall():
        for tag in ("White", "Black"):
            name = next((l.split('"')[1] for l in g["pgn"].splitlines() if l.startswith(f'[{tag} "')), None)
            if name:
                frontier.append((abs(g["my_rating"] - goal) if g["my_rating"] else 0, name.lower()))
    heapq.heapify(frontier)
    visited, requests = set(), 0
    today = dt.date.today()
    months = [(today.year, today.month), ((today.year if today.month > 1 else today.year - 1), (today.month - 1) or 12)]
    while frontier and requests < r["max_requests"] and any(have[tc] < r["games_per_class"] for tc in have):
        _, user = heapq.heappop(frontier)
        if user in visited:
            continue
        visited.add(user)
        for y, m in months:
            if requests >= r["max_requests"]:
                break
            requests += 1
            try:
                body = json.loads(client.get(f"{BASE}/player/{user}/games/{y}/{m:02d}")[2])
            except (FetchFailed, ValueError):
                continue
            for g in body.get("games", []):
                if g.get("rules") != "chess" or not g.get("rated"):
                    continue
                w, b = g["white"], g["black"]
                tc = g.get("time_class")
                needed = tc in have and have[tc] < r["games_per_class"]
                for opp in (w, b) if needed else ():  # follow only players from games of a class still needed
                    name = opp["username"].lower()
                    if name not in visited and opp.get("rating"):
                        heapq.heappush(frontier, (abs(opp["rating"] - goal), name))
                if needed and g.get("time_control") == r["time_controls"][tc] \
                        and lo <= (w.get("rating") or 0) <= hi and lo <= (b.get("rating") or 0) <= hi:
                    if import_game(conn, owner, g, source="reference") == "new":
                        have[tc] += 1
    ver = analysis_version()
    queued = 0
    for row in conn.execute("SELECT id, played_at FROM games WHERE source = 'reference' AND analysis_status = 'pending'").fetchall():
        queued += jobs.enqueue(conn, "analyze", f"analyze:{row['id']}:{ver}", {"game_id": row["id"]}, priority=5,
                               sort_key=row["played_at"].timestamp(), versions={"analysis": ver})
    return {"requests": requests, "players_visited": len(visited), "games": have, "jobs_enqueued": queued}
