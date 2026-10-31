"""Postgres access (psycopg 3). DATABASE_URL selects the database."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

MIGRATIONS = Path(__file__).parent / "migrations"


def url() -> str:
    return os.environ.get("DATABASE_URL", "postgresql://coach:coach@localhost/coach")


@contextmanager
def connect(autocommit: bool = False):
    with psycopg.connect(url(), row_factory=dict_row, autocommit=autocommit) as conn:
        yield conn


def migrate() -> list[str]:
    """Apply migrations in name order, once each. Idempotent."""
    applied = []
    with connect() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["name"] for r in conn.execute("SELECT name FROM schema_migrations")}
        for f in sorted(MIGRATIONS.glob("*.sql")):
            if f.name in done:
                continue
            conn.execute(f.read_text())
            conn.execute("INSERT INTO schema_migrations (name) VALUES (%s)", (f.name,))
            applied.append(f.name)
    return applied
