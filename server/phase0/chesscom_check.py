"""Phase 0 Appendix B1/B2: chess.com game counts and Published-Data API behavior checks.

Usage: python chesscom_check.py --out server/phase0/out

Serial requests only, User-Agent from coach.toml, ETag caching, backoff per §7.2 (all from coach.toml).
Writes archives/*.json (raw months), etags.json, checks.json and games.pgn (rated rapid + blitz,
with an added [TimeClass] header). This is a spike, not product code.
"""

from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import time
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[1] / "config" / "coach.toml"
BASE = "https://api.chess.com/pub"


def load_cfg():
    with open(CONFIG, "rb") as f:
        return tomllib.load(f)


class Client:
    def __init__(self, cfg):
        self.s = cfg["sync"]
        self.ua = self.s["user_agent"]
        self.log = []

    def get(self, url, etag=None, ua=True):
        """One request at a time; retry 429/5xx with 1 s doubling to 60 s, max 6 tries (§7.2)."""
        delay = self.s["backoff_initial_s"]
        for attempt in range(1, self.s["backoff_max_tries"] + 1):
            req = urllib.request.Request(url)
            if ua:
                req.add_header("User-Agent", self.ua)
            else:
                req.add_header("User-Agent", "")  # urllib otherwise sends Python-urllib/x.y
            if etag:
                req.add_header("If-None-Match", etag)
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    body = r.read()
                    self.log.append((url, r.status, attempt))
                    return r.status, {k.lower(): v for k, v in r.headers.items()}, body
            except urllib.error.HTTPError as e:
                self.log.append((url, e.code, attempt))
                if e.code == 304:
                    return 304, {k.lower(): v for k, v in e.headers.items()}, b""
                if e.code == 429 or e.code >= 500:
                    time.sleep(delay)
                    delay = min(delay * 2, self.s["backoff_max_s"])
                    continue
                return e.code, {k.lower(): v for k, v in e.headers.items()}, e.read()
        return None, {}, b""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    cfg = load_cfg()
    user = cfg["player"]["chesscom_username"]
    out = Path(args.out)
    (out / "archives").mkdir(parents=True, exist_ok=True)
    c = Client(cfg)
    checks = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(), "user_agent": c.ua}

    st, h, body = c.get(f"{BASE}/player/{user}")
    profile = json.loads(body)
    checks["profile"] = {k: profile.get(k) for k in ("player_id", "username", "joined", "status")}
    st, h, body = c.get(f"{BASE}/player/{user}/stats")
    (out / "stats.json").write_bytes(body)

    st, h, body = c.get(f"{BASE}/player/{user}/games/archives")
    months = json.loads(body)["archives"]
    checks["archive_count"] = len(months)
    etags, hashes, games = {}, {}, []
    for url in months:
        st, h, body = c.get(url)
        assert st == 200, (url, st)
        name = "-".join(url.rstrip("/").split("/")[-2:])
        (out / "archives" / f"{name}.json").write_bytes(body)
        etags[url] = h.get("etag")
        assert etags[url], url
        hashes[url] = sha(body)
        games += json.loads(body)["games"]
    (out / "etags.json").write_text(json.dumps({"etag": etags, "sha256": hashes}, indent=1))

    # Counts by time class: all time and last 90 days (by end_time).
    now = time.time()
    cut = now - 90 * 86400
    def count(gs):
        cnt = collections.Counter()
        for g in gs:
            key = (g.get("rules"), g.get("time_class"), "rated" if g.get("rated") else "unrated")
            cnt["|".join(map(str, key))] += 1
        return dict(sorted(cnt.items(), key=lambda kv: -kv[1]))
    checks["games_total"] = len(games)
    checks["counts_all_time"] = count(games)
    checks["counts_last_90_days"] = count([g for g in games if g.get("end_time", 0) >= cut])
    checks["first_game_end"] = dt.datetime.fromtimestamp(min(g["end_time"] for g in games), dt.timezone.utc).isoformat()
    checks["last_game_end"] = dt.datetime.fromtimestamp(max(g["end_time"] for g in games), dt.timezone.utc).isoformat()

    # Finished games only: current month has a result for both players, a Result tag != "*", and end_time.
    cur = [g for g in json.loads((out / "archives" / ("-".join(months[-1].rstrip("/").split("/")[-2:]) + ".json")).read_text())["games"]]
    unfinished = [g.get("url") for g in cur
                  if not g.get("end_time") or '[Result "*"]' in g.get("pgn", "")
                  or not g.get("white", {}).get("result") or not g.get("black", {}).get("result")]
    unfinished_all = [g.get("url") for g in games if '[Result "*"]' in g.get("pgn", "") or not g.get("end_time")]
    checks["current_month"] = {"url": months[-1], "games": len(cur), "unfinished": unfinished,
                               "unfinished_any_month": unfinished_all}

    # Past archives unchanged: re-fetch 3 old months with and without If-None-Match.
    old = months[: 3] if len(months) >= 6 else months[:1]
    refetch = []
    for url in old:
        st304, _, _ = c.get(url, etag=etags[url])
        st, h, body = c.get(url)
        refetch.append({"url": url, "conditional_status": st304, "etag_same": h.get("etag") == etags[url],
                        "body_sha256_same": sha(body) == hashes[url]})
    checks["old_month_refetch"] = refetch

    # User-Agent: one request with an empty UA.
    st, h, body = c.get(f"{BASE}/player/{user}", ua=False)
    checks["no_user_agent_status"] = st

    # games.pgn: rated rapid + blitz, standard chess, with TimeClass header for the benchmarks.
    n = 0
    with open(out / "games.pgn", "w") as f:
        for g in sorted(games, key=lambda g: g["end_time"]):
            if g.get("rules") == "chess" and g.get("rated") and g.get("time_class") in ("rapid", "blitz") and g.get("pgn"):
                f.write(f'[TimeClass "{g["time_class"]}"]\n' + g["pgn"].strip() + "\n\n")
                n += 1
    checks["games_pgn_count"] = n
    checks["requests"] = len(c.log)
    checks["retries"] = [x for x in c.log if x[2] > 1]
    (out / "checks.json").write_text(json.dumps(checks, indent=1))
    print(json.dumps({k: v for k, v in checks.items() if k != "current_month"}, indent=1))
    print("current month:", checks["current_month"]["games"], "unfinished:", checks["current_month"]["unfinished"])


if __name__ == "__main__":
    main()
