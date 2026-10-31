"""Version strings stored on derived rows (spec §8.5, §25 "Version change")."""

from __future__ import annotations

from coach.config import cfg

ENGINE = "Stockfish 18 (sf_18 cb3d4ee9)"


def analysis_version() -> str:
    e = cfg()["engine"]
    return f"sf18:{e['first_nodes']}/{e['played_nodes']}/{e['deep_nodes']}/{e['boundary_nodes']}:mpv{e['first_multipv']}:v1"
