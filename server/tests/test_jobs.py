"""Job queue (spec §25): idempotent keys, SKIP LOCKED claims, lease expiry, retries then failure."""

from coach import jobs


def test_enqueue_is_idempotent(db):
    assert jobs.enqueue(db, "analyze", "analyze:1:v1", {"game_id": 1})
    assert not jobs.enqueue(db, "analyze", "analyze:1:v1", {"game_id": 1})
    assert db.execute("SELECT count(*) AS n FROM jobs").fetchone()["n"] == 1


def test_priority_then_newest(db):
    jobs.enqueue(db, "analyze", "a", priority=1, sort_key=300)
    jobs.enqueue(db, "analyze", "b", priority=10, sort_key=100)
    jobs.enqueue(db, "analyze", "c", priority=10, sort_key=200)
    assert [jobs.claim(db)["key"] for _ in range(3)] == ["c", "b", "a"]
    assert jobs.claim(db) is None


def test_expired_lease_is_reclaimed(db):
    jobs.enqueue(db, "analyze", "x")
    j = jobs.claim(db)
    assert jobs.claim(db) is None                       # leased
    db.execute("UPDATE jobs SET lease_until = now() - interval '1 second' WHERE id = %s", (j["id"],))
    again = jobs.claim(db)
    assert again["id"] == j["id"] and again["attempts"] == 2


def test_fail_retries_then_marks_failed(db):
    jobs.enqueue(db, "analyze", "y")
    for attempt in (1, 2, 3):
        db.execute("UPDATE jobs SET run_after = now()")
        j = jobs.claim(db)
        assert j["attempts"] == attempt
        status = jobs.fail(db, j, RuntimeError("engine died"))
    assert status == "failed"
    row = db.execute("SELECT * FROM jobs").fetchone()
    assert row["status"] == "failed" and "engine died" in row["last_error"]


def test_concurrent_claims_do_not_collide(db):
    import psycopg
    from coach import db as dbmod
    jobs.enqueue(db, "analyze", "only")
    db.commit()
    with psycopg.connect(dbmod.url(), row_factory=psycopg.rows.dict_row) as a, psycopg.connect(dbmod.url(), row_factory=psycopg.rows.dict_row) as b:
        ja = jobs.claim(a)            # a holds the row lock (transaction open)
        jb = jobs.claim(b)            # SKIP LOCKED: b gets nothing
        assert ja is not None and jb is None
