"""Loads server/config/coach.toml. Every tunable comes from here (CLAUDE.md rule 2)."""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / "config" / "coach.toml"


@lru_cache(maxsize=1)
def cfg() -> dict:
    with open(os.environ.get("COACH_CONFIG", DEFAULT), "rb") as f:
        return tomllib.load(f)
