"""Postgres job queue (spec §25): natural keys make enqueueing idempotent; workers claim with
SELECT … FOR UPDATE SKIP LOCKED and a lease; a crashed worker's job is retried after the lease expires."""

from __future__ import annotations

import json
import traceback

from coach.config import cfg


def enqueue(conn, kind: str, key: str, payload: dict | None = None, priority: int = 0, sort_key: float = 0,
            versions: dict | None = None) -> bool:
    """Returns True if a new job was created; a duplicate key does nothing."""
    row = conn.execute(
        "INSERT INTO jobs (kind, key, payload, priority, sort_key, versions) VALUES (%s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (key) DO NOTHING RETURNING id",
        (kind, key, json.dumps(payload or {}), priority, sort_key, json.dumps(versions or {}))).fetchone()
    return row is not None


def claim(conn, kinds: list[str] | None = None) -> dict | None:
    lease = cfg()["jobs"]["lease_minutes"]
    row = conn.execute(
        f"""UPDATE jobs SET status = 'running', attempts = attempts + 1, updated_at = now(),
                lease_until = now() + make_interval(mins => %s)
            WHERE id = (
              SELECT id FROM jobs
              WHERE ((status = 'queued' AND run_after <= now()) OR (status = 'running' AND lease_until < now()))
                {"AND kind = ANY(%s)" if kinds else ""}
              ORDER BY priority DESC, sort_key DESC, id
              LIMIT 1 FOR UPDATE SKIP LOCKED)
            RETURNING *""",
        (lease, kinds) if kinds else (lease,)).fetchone()
    return row


def complete(conn, job_id: int) -> None:
    conn.execute("UPDATE jobs SET status = 'done', lease_until = NULL, last_error = NULL, updated_at = now() WHERE id = %s", (job_id,))


def fail(conn, job: dict, err: BaseException | str) -> str:
    """Retry with backoff until max_attempts, then mark failed (spec §25). Returns the new status."""
    msg = err if isinstance(err, str) else "".join(traceback.format_exception_only(type(err), err)).strip()
    status = "failed" if job["attempts"] >= cfg()["jobs"]["max_attempts"] else "queued"
    conn.execute(
        "UPDATE jobs SET status = %s, last_error = %s, lease_until = NULL, updated_at = now(), "
        "run_after = now() + make_interval(secs => %s) WHERE id = %s",
        (status, msg[:2000], cfg()["jobs"]["retry_backoff_s"] * job["attempts"], job["id"]))
    return status
