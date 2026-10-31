"""chess.com Published-Data API client (spec §7.1, §7.2): strictly serial, descriptive User-Agent, ETag
caching, retry 429/5xx with backoff from 1 s doubling to 60 s, at most 6 tries (all from coach.toml)."""

from __future__ import annotations

import threading
import time

import httpx

from coach.config import cfg

BASE = "https://api.chess.com/pub"
_LOCK = threading.Lock()  # one request at a time per process


class FetchFailed(Exception):
    pass


class Client:
    def __init__(self, transport: httpx.BaseTransport | None = None, sleep=time.sleep):
        s = cfg()["sync"]
        self.s, self.sleep = s, sleep
        self.http = httpx.Client(transport=transport, timeout=60, headers={"User-Agent": s["user_agent"]})

    def get(self, url: str, etag: str | None = None) -> tuple[int, str | None, bytes]:
        """Returns (status, etag, body). 304 means unchanged. Raises FetchFailed after max tries."""
        delay = self.s["backoff_initial_s"]
        last = None
        for _ in range(self.s["backoff_max_tries"]):
            with _LOCK:
                try:
                    r = self.http.get(url, headers={"If-None-Match": etag} if etag else {})
                    last = r.status_code
                except httpx.TransportError as e:
                    r, last = None, repr(e)
            if r is not None and r.status_code in (200, 304):
                return r.status_code, r.headers.get("etag") or etag, r.content
            if r is not None and r.status_code < 500 and r.status_code != 429:
                raise FetchFailed(f"{url}: HTTP {r.status_code}")
            self.sleep(delay)
            delay = min(delay * 2, self.s["backoff_max_s"])
        raise FetchFailed(f"{url}: gave up after {self.s['backoff_max_tries']} tries (last: {last})")

    def json(self, url: str) -> dict:
        import json
        return json.loads(self.get(url)[2])
