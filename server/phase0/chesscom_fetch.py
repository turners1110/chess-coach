"""Phase 0 chess.com fetcher (Appendix B1/B2). Strictly serial, per spec §7.2.

Downloads the profile, stats, archive list and every monthly archive into server/phase0/out/chesscom/,
keeping each response's ETag, and prints game counts by time class (all time and last N days).

Usage: python chesscom_fetch.py [--days 90]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import tomllib
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CFG = tomllib.load(open(ROOT / "config" / "coach.toml", "rb"))
OUT = ROOT / "phase0" / "out" / "chesscom"
BASE = "https://api.chess.com/pub"


def get(url: str, etag: str | None = None, user_agent: str | None = CFG["sync"]["user_agent"]):
    """One GET with §7.2 backoff on 429/5xx. Returns (status, headers, body bytes)."""
    s = CFG["sync"]
    delay = s["backoff_initial_s"]
    for attempt in range(s["backoff_max_tries"]):
        req = urllib.request.Request(url)
        if user_agent:
            req.add_header("User-Agent", user_agent)
        if etag:
            req.add_header("If-None-Match", etag)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return 304, dict(e.headers), b""
            if e.code == 429 or e.code >= 500:
                time.sleep(delay)
                delay = min(delay * 2, s["backoff_max_s"])
                continue
            return e.code, dict(e.headers), e.read()
    return -1, {}, b""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=90)
    a = ap.parse_args()
    user = CFG["player"]["chesscom_username"]
    OUT.mkdir(parents=True, exist_ok=True)
    meta = {}

    for name, url in [("profile", f"{BASE}/player/{user}"), ("stats", f"{BASE}/player/{user}/stats"),
                      ("archives", f"{BASE}/player/{user}/games/archives")]:
        st, h, body = get(url)
        (OUT / f"{name}.json").write_bytes(body)
        meta[name] = {"status": st, "etag": h.get("ETag") or h.get("Etag"), "last_modified": h.get("Last-Modified")}

    archives = json.loads((OUT / "archives.json").read_text())["archives"]
    for url in archives:  # serial, newest last as returned
        yyyymm = url.rsplit("/", 2)[-2] + url.rsplit("/", 1)[-1]
        st, h, body = get(url)
        (OUT / f"{yyyymm}.json").write_bytes(body)
        meta[yyyymm] = {"status": st, "etag": h.get("ETag") or h.get("Etag"), "bytes": len(body),
                        "sha256": hashlib.sha256(body).hexdigest(), "cache_control": h.get("Cache-Control"),
                        "last_modified": h.get("Last-Modified"), "fetched_at": datetime.now(timezone.utc).isoformat()}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1))

    cutoff = datetime.now(timezone.utc) - timedelta(days=a.days)
    all_time, recent, rated_all, rated_recent = Counter(), Counter(), Counter(), Counter()
    for f in sorted(OUT.glob("[0-9]" * 6 + ".json")):
        for g in json.loads(f.read_text()).get("games", []):
            tc = g.get("time_class", "?") + ("" if g.get("rules", "chess") == "chess" else f"/{g['rules']}")
            all_time[tc] += 1
            rated_all[tc] += bool(g.get("rated"))
            if datetime.fromtimestamp(g["end_time"], timezone.utc) >= cutoff:
                recent[tc] += 1
                rated_recent[tc] += bool(g.get("rated"))
    print(json.dumps({"archives": len(archives), "all_time": all_time, "rated_all_time": rated_all,
                      f"last_{a.days}_days": recent, f"rated_last_{a.days}_days": rated_recent}, indent=1))


if __name__ == "__main__":
    main()
