"""Worker: runs queued jobs (analysis; sync on a schedule). Start one process per engine (`engine.workers`)."""

from __future__ import annotations

import argparse
import logging
import multiprocessing as mp
import time

from coach import analysis, db, importer, jobs, reference, tablebase
from coach.chesscom import Client
from coach.config import cfg

log = logging.getLogger("coach.worker")


def run_one(eng: analysis.Engine, tb: tablebase.Tablebase | None) -> bool:
    """Claims and runs one analysis job. Returns False when the queue is empty."""
    with db.connect() as conn:
        job = jobs.claim(conn, ["analyze"])
        conn.commit()
        if not job:
            return False
        gid = job["payload"]["game_id"]
        try:
            r = analysis.analyse_game(conn, gid, eng, tb)
            jobs.complete(conn, job["id"])
            conn.commit()
            log.info("analyzed game %s (%s plies)", gid, r["plies"])
        except Exception as e:  # noqa: BLE001 - recorded on the job (§25)
            conn.rollback()
            status = jobs.fail(conn, job, e)
            if status == "failed":
                conn.execute("UPDATE games SET analysis_status = 'failed' WHERE id = %s", (gid,))
            conn.commit()
            log.exception("game %s failed (%s)", gid, status)
            try:  # restart the engine after an error (§25)
                eng.close()
            except Exception:  # noqa: BLE001
                pass
            eng.__init__(eng.path)
    return True


def analysis_loop(idle_s: float = 10) -> None:
    eng, tb = analysis.Engine(), tablebase.Tablebase()
    try:
        while True:
            if not run_one(eng, tb):
                time.sleep(idle_s)
    finally:
        eng.close()


def sync_once(resync: list[str] | None = None) -> dict:
    client = Client()
    with db.connect() as conn:
        s = importer.sync(conn, client, resync=resync)
        conn.commit()
        # The report card's goal-level reference set (§12.10): built once, topped up if short
        r = cfg()["reference"]
        have = conn.execute("SELECT time_class, count(*) AS n FROM games WHERE source = 'reference' GROUP BY 1").fetchall()
        counts = {x["time_class"]: x["n"] for x in have}
        if any(counts.get(tc, 0) < r["games_per_class"] for tc in r["time_classes"]):
            s["reference"] = reference.build(conn, client)
            conn.commit()
    log.info("sync: %s", s)
    return s


def run_sync_jobs() -> None:
    """Runs syncs queued by the API (manual sync, resync month)."""
    while True:
        with db.connect() as conn:
            job = jobs.claim(conn, ["sync"])
            conn.commit()
            if not job:
                return
            try:
                sync_once(job["payload"].get("resync") or None)
                jobs.complete(conn, job["id"])
            except Exception as e:  # noqa: BLE001
                jobs.fail(conn, job, e)
            conn.commit()


def main() -> None:
    ap = argparse.ArgumentParser(description="Chess Coach worker")
    ap.add_argument("--workers", type=int, default=None, help="analysis processes (default engine.workers)")
    ap.add_argument("--no-sync", action="store_true", help="do not poll chess.com")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(processName)s %(message)s")
    db.migrate()
    n = a.workers or cfg()["engine"]["workers"]
    procs = [mp.Process(target=analysis_loop, name=f"analysis-{k}", daemon=True) for k in range(n)]
    for p in procs:
        p.start()
    if a.no_sync:
        for p in procs:
            p.join()
        return
    import datetime

    from apscheduler.executors.pool import ThreadPoolExecutor
    from apscheduler.schedulers.blocking import BlockingScheduler
    # One thread: scheduled polls and queued manual syncs never overlap, so chess.com requests stay serial (§7.2)
    sched = BlockingScheduler(executors={"default": ThreadPoolExecutor(1)}, job_defaults={"coalesce": True, "max_instances": 1})
    sched.add_job(sync_once, "interval", minutes=cfg()["sync"]["poll_minutes"], next_run_time=datetime.datetime.now())
    sched.add_job(run_sync_jobs, "interval", seconds=30)
    sched.start()


if __name__ == "__main__":
    main()
