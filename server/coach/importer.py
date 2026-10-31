"""chess.com import (spec §7.3, §7.4): profile, rating snapshot, monthly archives (ETag), games and plies.
Then analysis jobs: the most recent games per time class first, the rest newest-first at low priority."""

from __future__ import annotations

import datetime as dt
import io
import json

import chess
import chess.pgn

from coach import jobs
from coach.chesscom import BASE, Client
from coach.config import cfg
from coach.positions import position_key
from coach.versions import analysis_version

DRAWS = {"agreed", "repetition", "stalemate", "insufficient", "50move", "timevsinsufficient"}


def ensure_player(conn, username: str) -> dict:
    conn.execute("INSERT INTO players (chesscom_username) VALUES (%s) ON CONFLICT DO NOTHING", (username,))
    return conn.execute("SELECT * FROM players WHERE chesscom_username = %s", (username,)).fetchone()


def sync(conn, client: Client, username: str | None = None, resync: list[str] | None = None) -> dict:
    """One sync cycle. Past months already done are skipped unless listed in `resync` (yyyymm)."""
    username = username or cfg()["player"]["chesscom_username"]
    player = ensure_player(conn, username)
    prof = client.json(f"{BASE}/player/{username}")
    conn.execute("UPDATE players SET chesscom_player_id = %s, updated_at = now() WHERE id = %s", (prof.get("player_id"), player["id"]))
    stats = client.json(f"{BASE}/player/{username}/stats")
    today = dt.datetime.now(dt.timezone.utc).date()
    for tc in ("rapid", "blitz", "bullet"):
        last = (stats.get(f"chess_{tc}") or {}).get("last")
        if last:
            conn.execute("INSERT INTO ratings_history (player_id, time_class, date, rating) VALUES (%s, %s, %s, %s) "
                         "ON CONFLICT (player_id, time_class, date) DO UPDATE SET rating = EXCLUDED.rating, updated_at = now()",
                         (player["id"], tc, today, last["rating"]))
    urls = client.json(f"{BASE}/player/{username}/games/archives")["archives"]
    summary = {"months_fetched": 0, "months_unchanged": 0, "games_new": 0, "games_failed": 0}
    for i, url in enumerate(urls):
        yyyymm = "".join(url.rstrip("/").split("/")[-2:])
        row = conn.execute("SELECT * FROM archives WHERE player_id = %s AND yyyymm = %s", (player["id"], yyyymm)).fetchone()
        current = i == len(urls) - 1
        if row and row["status"] == "done" and not current and yyyymm not in (resync or []):
            continue
        etag = row["etag"] if row and row["status"] == "done" else None
        try:
            status, new_etag, body = client.get(url, etag)
        except Exception as e:  # noqa: BLE001 - recorded on the archive, retried next cycle
            conn.execute("INSERT INTO archives (player_id, yyyymm, url, status, error) VALUES (%s, %s, %s, 'failed', %s) "
                         "ON CONFLICT (player_id, yyyymm) DO UPDATE SET status = 'failed', error = EXCLUDED.error, updated_at = now()",
                         (player["id"], yyyymm, url, str(e)))
            continue
        if status == 304:
            summary["months_unchanged"] += 1
        else:
            summary["months_fetched"] += 1
            for g in json.loads(body)["games"]:
                r = import_game(conn, player, g)
                if r == "new":
                    summary["games_new"] += 1
                elif r == "failed":
                    summary["games_failed"] += 1
        conn.execute("INSERT INTO archives (player_id, yyyymm, url, etag, last_fetched, status) VALUES (%s, %s, %s, %s, now(), 'done') "
                     "ON CONFLICT (player_id, yyyymm) DO UPDATE SET etag = EXCLUDED.etag, last_fetched = now(), status = 'done', error = NULL, updated_at = now()",
                     (player["id"], yyyymm, url, new_etag))
    summary["jobs_enqueued"] = enqueue_analysis(conn, player["id"])
    return summary


def _move_tokens(pgn: str) -> int:
    """Counts SAN tokens in the main line of a single-game PGN (comments, variations, NAGs, numbers, result removed)."""
    import re
    text = "\n".join(l for l in pgn.splitlines() if not l.startswith("["))
    text = re.sub(r"\{[^}]*\}", " ", text)
    while re.search(r"\([^()]*\)", text):
        text = re.sub(r"\([^()]*\)", " ", text)
    toks = [t for t in text.split() if not re.fullmatch(r"\d+\.+|\$\d+|1-0|0-1|1/2-1/2|\*", t)]
    toks = [re.sub(r"^\d+\.+", "", t) for t in toks]
    return sum(1 for t in toks if t)


def _result(side: dict) -> str:
    r = side.get("result")
    return "win" if r == "win" else "draw" if r in DRAWS else "loss"


def import_game(conn, player: dict, g: dict) -> str:
    """Returns 'new', 'exists', 'skipped' or 'failed'. Variants and unrated games are skipped (§7.4)."""
    if g.get("rules") != "chess" or not g.get("rated"):
        return "skipped"
    url = g["url"]
    if conn.execute("SELECT 1 FROM games WHERE chesscom_url = %s", (url,)).fetchone():
        return "exists"
    me = player["chesscom_username"].lower()
    color = "w" if g["white"]["username"].lower() == me else "b"
    mine, opp = (g["white"], g["black"]) if color == "w" else (g["black"], g["white"])
    base = {"player_id": player["id"], "chesscom_url": url, "time_class": g["time_class"], "time_control": g["time_control"],
            "rated": True, "played_at": dt.datetime.fromtimestamp(g["end_time"], dt.timezone.utc), "color": color,
            "my_rating": mine.get("rating"), "opp_rating": opp.get("rating"), "opponent": opp.get("username"),
            "result": _result(mine), "pgn": g.get("pgn", "")}
    try:
        game = chess.pgn.read_game(io.StringIO(base["pgn"]))
        if game is None or game.errors:
            raise ValueError(f"PGN errors: {game.errors if game else 'empty'}")
        h = game.headers
        board = game.board()
        moves = list(game.mainline())
        tokens = _move_tokens(base["pgn"])
        if tokens != len(moves):  # python-chess silently skips tokens it cannot read
            raise ValueError(f"PGN has {tokens} move tokens but {len(moves)} parsed moves")
        base.update(termination=h.get("Termination"), eco=h.get("ECO"),
                    opening=(h.get("ECOUrl") or "").rstrip("/").split("/")[-1].replace("-", " ") or None, n_plies=len(moves))
    except Exception as e:  # noqa: BLE001 - corrupt PGNs are stored with the error and never block a batch
        conn.execute("INSERT INTO games (player_id, chesscom_url, time_class, time_control, rated, played_at, color, my_rating, opp_rating, "
                     "opponent, result, pgn, parse_status, parse_error, analysis_status) VALUES (%(player_id)s, %(chesscom_url)s, %(time_class)s, "
                     "%(time_control)s, %(rated)s, %(played_at)s, %(color)s, %(my_rating)s, %(opp_rating)s, %(opponent)s, %(result)s, %(pgn)s, "
                     "'failed', %(err)s, 'skipped')", {**base, "err": str(e)[:500]})
        return "failed"
    imp = cfg()["import"]
    analyze = g["time_class"] in imp["analyze_time_classes"] and len(moves) >= imp["min_plies"]
    gid = conn.execute(
        "INSERT INTO games (player_id, chesscom_url, time_class, time_control, rated, played_at, color, my_rating, opp_rating, opponent, "
        "result, termination, eco, opening, pgn, n_plies, analysis_status) VALUES (%(player_id)s, %(chesscom_url)s, %(time_class)s, "
        "%(time_control)s, %(rated)s, %(played_at)s, %(color)s, %(my_rating)s, %(opp_rating)s, %(opponent)s, %(result)s, %(termination)s, "
        "%(eco)s, %(opening)s, %(pgn)s, %(n_plies)s, %(status)s) RETURNING id",
        {**base, "status": "pending" if analyze else "skipped"}).fetchone()["id"]
    tc = g["time_control"]
    daily = "/" in tc
    base_s, inc_s = (0, 0) if daily else (int(tc.split("+")[0]), int(tc.split("+")[1]) if "+" in tc else 0)
    last_clock = {chess.WHITE: base_s * 1000, chess.BLACK: base_s * 1000}
    rows, pos = [], []
    for ply, node in enumerate(moves):
        mover = board.turn
        norm, z = position_key(board)
        clk = node.clock()
        clock_ms = None if clk is None or daily else round(clk * 1000)
        spent = None
        if clock_ms is not None:
            spent = last_clock[mover] - clock_ms + inc_s * 1000
            last_clock[mover] = clock_ms
        pos.append((norm, z))
        rows.append((gid, ply, norm, board.fen(), board.san(node.move), node.move.uci(), clock_ms, spent,
                     (mover == chess.WHITE) == (color == "w")))
        board.push(node.move)
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO positions (fen_norm, zobrist) VALUES (%s, %s) ON CONFLICT DO NOTHING", pos)
        cur.executemany("INSERT INTO plies (game_id, ply, fen_norm_before, fen_before, san, uci, clock_ms, time_spent_ms, mover_is_me) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)", rows)
    return "new"


def enqueue_analysis(conn, player_id: int) -> int:
    """§7.3: the most recent N games per analyzed time class first (high priority), then the rest newest-first."""
    n = cfg()["import"]["initial_games_per_class"]
    ver = analysis_version()
    rows = conn.execute(
        "SELECT id, played_at, row_number() OVER (PARTITION BY time_class ORDER BY played_at DESC) AS rn "
        "FROM games WHERE player_id = %s AND analysis_status = 'pending'", (player_id,)).fetchall()
    made = 0
    for r in rows:
        made += jobs.enqueue(conn, "analyze", f"analyze:{r['id']}:{ver}", {"game_id": r["id"]},
                             priority=10 if r["rn"] <= n else 1, sort_key=r["played_at"].timestamp(), versions={"analysis": ver})
    return made
