"""Engine analysis of one game (spec §8): first, played-move, deep and boundary passes; tablebase for <= 5
pieces; Win%, win_loss, eval_delta, classes, labels, suppression, context tags, GRI and lila accuracy.
Searches are cached in engine_evals by (fen_norm, pass, engine version, build hash, nodes)."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from functools import lru_cache

import chess
import chess.engine

from coach import accuracy, tablebase
from coach.config import cfg
from coach.versions import ENGINE, analysis_version
from coach.winpct import win_from_score

VAL = {chess.PAWN: 1, chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9, chess.KING: 0}


@lru_cache(maxsize=4)
def build_hash(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


class Engine:
    """One Stockfish process (Threads from config, Hash from config); `ucinewgame` per game via the game key."""

    def __init__(self, path: str | None = None):
        self.path = path or os.environ.get("STOCKFISH", "stockfish")
        e = cfg()["engine"]
        self.settings = {"Threads": e["threads"], "Hash": e["hash_mb"]}
        self.proc = chess.engine.SimpleEngine.popen_uci(self.path)
        self.proc.configure(self.settings)
        self.build = build_hash(_which(self.path))
        self.cpu = cpu_model()

    def close(self):
        self.proc.quit()

    def search(self, conn, board: chess.Board, fen_norm: str, pass_: str, nodes: int, multipv: int = 1,
               root_moves: list[chess.Move] | None = None, game_key=None) -> list[dict]:
        row = conn.execute("SELECT lines FROM engine_evals WHERE fen_norm = %s AND pass = %s AND engine_version = %s "
                           "AND build_hash = %s AND nodes = %s", (fen_norm, pass_, ENGINE, self.build, nodes)).fetchone()
        if row:
            return row["lines"]
        infos = self.proc.analyse(board, chess.engine.Limit(nodes=nodes), multipv=multipv, root_moves=root_moves, game=game_key)
        lines = []
        for i in infos:
            if not i.get("pv"):
                continue
            s = i["score"].pov(board.turn)
            lines.append({"pv": [m.uci() for m in i["pv"][:12]], **({"mate": s.mate()} if s.is_mate() else {"cp": s.score()})})
        conn.execute("INSERT INTO engine_evals (fen_norm, pass, engine_version, build_hash, nodes, settings, cpu_model, lines) "
                     "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING",
                     (fen_norm, pass_, ENGINE, self.build, nodes, json.dumps({**self.settings, "multipv": multipv}), self.cpu, json.dumps(lines)))
        return lines


def _which(path: str) -> str:
    import shutil
    return shutil.which(path) or path


def win(line: dict) -> float:
    return win_from_score(cp=line.get("cp"), mate=line.get("mate"))


def classify(win_loss: float) -> str:
    c = cfg()["classes"]
    return "blunder" if win_loss >= c["blunder"] else "mistake" if win_loss >= c["mistake"] else "inaccuracy" if win_loss >= c["inaccuracy"] else "good"


def near_boundary(win_loss: float, gap: float | None) -> bool:
    e, c = cfg()["engine"], cfg()["classes"]
    m = e["boundary_margin"]
    if any(abs(win_loss - b) <= m for b in (c["inaccuracy"], c["mistake"], c["blunder"])):
        return True
    return gap is not None and abs(gap - cfg()["labels"]["unique_gap"]) <= m


def phase_of(board: chess.Board, ply: int) -> str:
    p = cfg()["phase"]
    if ply < p["opening_max_ply"]:
        return "opening"
    non_pawn = sum(VAL[pc.piece_type] for pc in board.piece_map().values() if pc.piece_type not in (chess.PAWN, chess.KING))
    return "endgame" if non_pawn <= p["endgame_non_pawn_max"] else "middlegame"


def _deep_scores(lines: list[dict], played: str) -> tuple[float, float, float | None]:
    wins = {l["pv"][0]: win(l) for l in lines}
    ordered = sorted(wins.values(), reverse=True)
    gap = ordered[0] - ordered[1] if len(ordered) > 1 else None
    return ordered[0], wins.get(played, ordered[-1]), gap


def score_move(conn, eng: Engine, tb: tablebase.Tablebase | None, board: chess.Board, fen_norm: str, played: chess.Move,
               mover_is_me: bool, game_key) -> dict:
    e = cfg()["engine"]
    pu = played.uci()
    # Tablebase substitution (§8.3)
    if tb is not None and tablebase.applies(board):
        t = tb.probe(conn, board, fen_norm)
        cat = tablebase.move_category(t, pu) if t else None
        if t and cat is not None and t["best_uci"]:
            wb = tablebase.win_pct(t["category"])
            wp = 100 - tablebase.win_pct(cat)
            return {"best_uci": t["best_uci"], "win_best": wb, "win_played": wp, "win_loss": max(0.0, wb - wp),
                    "first_win_loss": max(0.0, wb - wp), "eval_delta": 0.0, "final_pass": "tablebase", "gap": None,
                    "best_line": [t["best_uci"]], "mate": False}
    first = eng.search(conn, board, fen_norm, "first", e["first_nodes"], e["first_multipv"], game_key=game_key)
    wins = {l["pv"][0]: win(l) for l in first}
    top = [l["pv"][0] for l in first]
    win_best = max(wins.values())
    if pu in wins:
        win_played = wins[pu]
    else:
        pl = eng.search(conn, board, fen_norm, f"played:{pu}", e["played_nodes"], 1, root_moves=[played], game_key=game_key)
        win_played = win(pl[0])
    first_wl = max(0.0, win_best - win_played)
    ordered = sorted(wins.values(), reverse=True)
    gap = ordered[0] - ordered[1] if len(ordered) > 1 else None
    final_wl, final_pass, best_uci, best_line = first_wl, "first", top[0], first[0]["pv"]
    mate = any("mate" in l and l["mate"] > 0 for l in first[:1])
    threshold = e["deep_min_win_loss_me"] if mover_is_me else e["deep_min_win_loss_opp"]
    if first_wl >= threshold:
        cand = list(dict.fromkeys(top[: e["deep_top_k"]] + [pu]))
        key = "deep:" + ",".join(sorted(cand))
        deep = eng.search(conn, board, fen_norm, key, e["deep_nodes"], len(cand), root_moves=[chess.Move.from_uci(u) for u in cand], game_key=game_key)
        win_best, win_played, gap = _deep_scores(deep, pu)
        final_wl, final_pass, best_uci, best_line = max(0.0, win_best - win_played), "deep", deep[0]["pv"][0], deep[0]["pv"]
        mate = "mate" in deep[0] and deep[0]["mate"] > 0
        if near_boundary(final_wl, gap):
            b = eng.search(conn, board, fen_norm, "boundary:" + ",".join(sorted(cand)), e["boundary_nodes"], len(cand),
                           root_moves=[chess.Move.from_uci(u) for u in cand], game_key=game_key)
            win_best, win_played, gap = _deep_scores(b, pu)
            final_wl, final_pass, best_uci, best_line = max(0.0, win_best - win_played), "boundary", b[0]["pv"][0], b[0]["pv"]
            mate = "mate" in b[0] and b[0]["mate"] > 0
    return {"best_uci": best_uci, "win_best": win_best, "win_played": win_played, "win_loss": final_wl, "first_win_loss": first_wl,
            "eval_delta": abs(final_wl - first_wl), "final_pass": final_pass, "gap": gap, "best_line": best_line, "mate": mate,
            "first_lines": first}


def labels_for(s: dict) -> list[str]:
    lab, sup = cfg()["labels"], cfg()["suppression"]
    out = []
    if s["win_best"] >= lab["missed_win_best_min"] and s["win_played"] <= lab["missed_win_played_max"]:
        out.append("missed_win")
    if s["gap"] is not None and s["gap"] >= lab["unique_gap"]:
        out.append("unique_solution")
    if s["win_loss"] < lab["acceptable"]:
        out.append("acceptable")
    hi, lo = sup["decided_high"], sup["decided_low"]
    if (s["win_best"] > hi and s["win_played"] > hi) or (s["win_best"] < lo and s["win_played"] < lo):
        out.append("suppressed")
    return out


def context_tags(game: dict, plies: list[dict], i: int, board: chess.Board, move: chess.Move, seen: dict) -> list[str]:
    c = cfg()["context"]
    tags = []
    p = plies[i]
    tc = game["time_control"]
    if "/" not in tc and p["clock_ms"] is not None:
        base = int(tc.split("+")[0]) * 1000
        prev_own = next((plies[j]["clock_ms"] for j in range(i - 2, -1, -2) if plies[j]["clock_ms"] is not None), base)
        if prev_own < c["time_pressure_pct"] * base or prev_own < c["time_pressure_s"] * 1000:
            tags.append("time_pressure")
        if p["time_spent_ms"] is not None and p["time_spent_ms"] < c["fast_s"] * 1000 and prev_own > c["fast_min_remaining_s"] * 1000:
            tags.append("fast_move")
    if i > 0:
        prev = chess.Board(plies[i - 1]["fen_before"])
        pm = chess.Move.from_uci(plies[i - 1]["uci"])
        if prev.is_capture(pm):
            tags.append("after_opponent_capture")
        if prev.gives_check(pm):
            tags.append("after_opponent_check")
    tags.append("move_type:" + ("check" if board.gives_check(move) else "capture" if board.is_capture(move) else "quiet"))
    tags.append("piece_moved:" + chess.piece_name(board.piece_type_at(move.from_square)))
    if seen.get(p["fen_norm_before"], 0) > 1:
        tags.append("repeated_position")
    return tags


def analyse_game(conn, game_id: int, eng: Engine, tb: tablebase.Tablebase | None) -> dict:
    game = conn.execute("SELECT * FROM games WHERE id = %s", (game_id,)).fetchone()
    plies = conn.execute("SELECT * FROM plies WHERE game_id = %s ORDER BY ply", (game_id,)).fetchall()
    ver = analysis_version()
    gk = f"game-{game_id}"
    seen: dict[str, int] = {}
    rows, cps = [], [accuracy.LEGACY_INITIAL_CP]
    gri_mult = cfg()["gri"]["motif_mult"]
    for i, p in enumerate(plies):
        seen[p["fen_norm_before"]] = seen.get(p["fen_norm_before"], 0) + 1
        board = chess.Board(p["fen_before"])
        move = chess.Move.from_uci(p["uci"])
        s = score_move(conn, eng, tb, board, p["fen_norm_before"], move, p["mover_is_me"], gk)
        labels = labels_for(s)
        cls = classify(s["win_loss"])
        rows.append({"game_id": game_id, "ply": i, "mover_is_me": p["mover_is_me"], "best_uci": s["best_uci"],
                     "win_best": s["win_best"], "win_played": s["win_played"], "win_loss": s["win_loss"],
                     "first_win_loss": s["first_win_loss"], "eval_delta": s["eval_delta"], "final_pass": s["final_pass"],
                     "class": cls, "labels": labels, "gap": s["gap"],
                     "gri": s["win_loss"] * (gri_mult if s["mate"] else 1.0),
                     "context_tags": context_tags(game, plies, i, board, move, seen), "best_line": s["best_line"],
                     "refutation": None, "analysis_version": ver})
    # Accuracy and refutations need the eval of each position after the move: reuse the next ply's first pass.
    final = chess.Board(plies[-1]["fen_before"])
    final.push(chess.Move.from_uci(plies[-1]["uci"]))
    for i, p in enumerate(plies):
        if i + 1 < len(plies):
            nb = chess.Board(plies[i + 1]["fen_before"])
            nxt = eng.search(conn, nb, plies[i + 1]["fen_norm_before"], "first", cfg()["engine"]["first_nodes"], cfg()["engine"]["first_multipv"], game_key=gk) \
                if not (tb and tablebase.applies(nb)) else None
            if nxt:
                rows[i]["refutation"] = nxt[0]["pv"][:8]
                if nxt[0].get("mate", 0) > 0:  # the reply mates: mate is involved (§12.1)
                    rows[i]["gri"] = rows[i]["win_loss"] * gri_mult
                stm_cp = _force_cp(nxt[0])
            else:  # tablebase position: map its Win% back to the clamp scale for accuracy purposes
                stm_cp = _tb_cp(rows[i + 1]["win_best"])
            cps.append(stm_cp if nb.turn == chess.WHITE else -stm_cp)
        else:
            cps.append(_terminal_cp(final))
    acc = accuracy.game_accuracy(chess.Board(plies[0]["fen_before"]).turn == chess.WHITE, cps)
    me_white = game["color"] == "w"
    acc_me = acc and acc["white" if me_white else "black"]
    acc_opp = acc and acc["black" if me_white else "white"]
    with conn.cursor() as cur:
        cur.execute("DELETE FROM move_scores WHERE game_id = %s", (game_id,))
        cur.executemany(
            "INSERT INTO move_scores (game_id, ply, mover_is_me, best_uci, win_best, win_played, win_loss, first_win_loss, eval_delta, "
            "final_pass, class, labels, gap, gri, context_tags, best_line, refutation, analysis_version) VALUES (%(game_id)s, %(ply)s, "
            "%(mover_is_me)s, %(best_uci)s, %(win_best)s, %(win_played)s, %(win_loss)s, %(first_win_loss)s, %(eval_delta)s, %(final_pass)s, "
            "%(class)s, %(labels)s, %(gap)s, %(gri)s, %(context_tags)s, %(best_line)s, %(refutation)s, %(analysis_version)s)", rows)
        cur.execute("UPDATE games SET analysis_status = 'done', accuracy_me = %s, accuracy_opp = %s, updated_at = now() WHERE id = %s",
                    (acc_me, acc_opp, game_id))
    return {"game_id": game_id, "plies": len(plies), "accuracy": acc}


def _force_cp(line: dict) -> int:
    if "mate" in line:
        return accuracy.force_as_cp(line["mate"]) if line["mate"] != 0 else accuracy.force_as_cp(-1)
    return line["cp"]


def _tb_cp(w: float) -> int:
    clamp = cfg()["engine"]["cp_clamp"]
    return clamp if w >= 100 else -clamp if w <= 0 else 0


def _terminal_cp(board: chess.Board) -> int:
    """White-POV cp for the final position: checkmate counts as a forced mate, other game ends as 0."""
    if board.is_checkmate():
        return accuracy.force_as_cp(-1) if board.turn == chess.WHITE else accuracy.force_as_cp(1)
    return 0
