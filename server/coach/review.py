"""Game review moments (spec §12.1): Sam's largest objective swing first, then the next highest-GRI moves,
then opponent mistakes Sam failed to punish."""

from __future__ import annotations

from coach.config import cfg


def flagged(m: dict) -> bool:
    return m["class"] != "good" and "suppressed" not in m["labels"]


def moments(scores: list[dict]) -> list[dict]:
    g = cfg()["gri"]
    mine = [m for m in scores if m["mover_is_me"]]
    if not mine:
        return []
    out = []
    largest = max(mine, key=lambda m: (m["win_loss"], -m["ply"]))
    out.append({"kind": "largest_swing", **largest})
    rest = sorted((m for m in mine if m is not largest and flagged(m)), key=lambda m: (-m["gri"], m["ply"]))
    out += [{"kind": "important", **m} for m in rest[: g["review_top_n"]]]
    by_ply = {m["ply"]: m for m in scores}
    unpunished = []
    for m in scores:
        if m["mover_is_me"] or m["class"] not in ("mistake", "blunder") or "suppressed" in m["labels"]:
            continue
        reply = by_ply.get(m["ply"] + 1)
        if reply and reply["win_loss"] >= g["unpunished_min_loss"]:
            unpunished.append({"kind": "unpunished", **m, "reply_ply": reply["ply"], "reply_loss": reply["win_loss"]})
    unpunished.sort(key=lambda m: (-m["win_loss"], m["ply"]))
    out += unpunished[: g["review_opp_n"]]
    return out
