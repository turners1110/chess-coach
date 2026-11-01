"""Lichess tablebase API (spec §8.3, §16.2): positions with <= max_pieces pieces. Serial, cached in tb_results.
Returns None on any failure so the caller falls back to the engine (spec §25 degradation)."""

from __future__ import annotations

import json
import threading

import chess
import httpx

from coach.config import cfg

_LOCK = threading.Lock()
WDL = {"win": 2, "cursed-win": 1, "draw": 0, "blessed-loss": -1, "loss": -2, "maybe-win": 1, "maybe-loss": -1}


def applies(board: chess.Board) -> bool:
    return len(board.piece_map()) <= cfg()["tablebase"]["max_pieces"] and not board.castling_rights


def win_pct(category: str) -> float:
    """Tablebase Win% for the side to move (§8.3): win 100, draw 50, loss 0. Cursed wins and blessed losses
    are draws under the 50-move rule."""
    w = WDL.get(category, 0)
    return 100.0 if w == 2 else 0.0 if w == -2 else 50.0


class Tablebase:
    def __init__(self, transport: httpx.BaseTransport | None = None):
        t = cfg()["tablebase"]
        self.url = t["api_url"]
        self.http = httpx.Client(transport=transport, timeout=t["timeout_s"], headers={"User-Agent": cfg()["sync"]["user_agent"]})

    def probe(self, conn, board: chess.Board, fen_norm: str) -> dict | None:
        row = conn.execute("SELECT * FROM tb_results WHERE fen_norm = %s", (fen_norm,)).fetchone()
        if row:
            return row
        try:
            with _LOCK:
                r = self.http.get(self.url, params={"fen": board.fen()})
            if r.status_code != 200:
                return None
            d = r.json()
        except (httpx.HTTPError, ValueError):
            return None
        if d.get("category") in (None, "unknown"):
            return None
        moves = [{"uci": m["uci"], "category": m["category"], "dtz": m.get("dtz")} for m in d.get("moves", [])]
        row = {"fen_norm": fen_norm, "wdl": WDL.get(d["category"]), "dtz": d.get("dtz"), "category": d["category"],
               "source": "lichess-api", "best_uci": moves[0]["uci"] if moves else None, "moves": moves}
        conn.execute("INSERT INTO tb_results (fen_norm, wdl, dtz, category, source, best_uci, moves) VALUES "
                     "(%(fen_norm)s, %(wdl)s, %(dtz)s, %(category)s, %(source)s, %(best_uci)s, %(moves)s) ON CONFLICT DO NOTHING",
                     {**row, "moves": json.dumps(moves)})
        return row


def move_category(tb: dict, uci: str) -> str | None:
    """Category for the side to move *after* `uci` (the API reports moves from the opponent's view)."""
    for m in tb["moves"] if isinstance(tb["moves"], list) else json.loads(tb["moves"]):
        if m["uci"] == uci:
            return m["category"]
    return None
