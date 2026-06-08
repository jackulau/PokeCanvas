"""Tiny in-memory sliding-window rate limiter.

Protects a shared (multi-tenant) deployment and the upstream Canvas API from a
single user hammering it. Keyed per Poke user (X-Poke-User-Id). The clock is
injectable for deterministic tests.

Note: in-memory = per-process. A multi-instance deployment that needs a global
limit should back this with Redis; documented in SECURITY.md.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        max_requests: int = 120,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._clock = clock
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        """Record a hit for `key`; return False if it exceeds the window limit."""
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.max_requests:
                return False
            hits.append(now)
            return True
