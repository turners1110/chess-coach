import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_DB = os.environ.get("TEST_DATABASE_URL", "postgresql://coach:coach@localhost/coach_test")


@pytest.fixture()
def db(monkeypatch):
    """A clean Phase 1 schema in the test database (skips when Postgres is not reachable)."""
    psycopg = pytest.importorskip("psycopg")
    try:
        with psycopg.connect(TEST_DB, autocommit=True) as c:
            c.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
    except psycopg.OperationalError as e:
        pytest.skip(f"Postgres not available: {e}")
    monkeypatch.setenv("DATABASE_URL", TEST_DB)
    from coach import db as dbmod
    dbmod.migrate()
    with dbmod.connect() as conn:
        yield conn
