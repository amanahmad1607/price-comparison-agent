"""
src/infrastructure/rate_limiter.py
------------------------------------
Token-bucket rate limiter — one bucket per platform (zepto, blinkit).
"""
from __future__ import annotations
import asyncio, time
from collections import defaultdict


class RateLimiter:
    _DEFAULT = {"rate": 20, "period": 60}

    def __init__(self, limits: dict[str, dict]):
        self._limits = limits
        self._tokens: dict[str, float] = defaultdict(float)
        self._last_refill: dict[str, float] = defaultdict(time.monotonic)
        self._locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    def _refill(self, platform: str) -> None:
        cfg    = self._limits.get(platform, self._DEFAULT)
        now    = time.monotonic()
        elapsed = now - self._last_refill[platform]
        added  = elapsed * (cfg["rate"] / cfg["period"])
        self._tokens[platform] = min(float(cfg["rate"]), self._tokens[platform] + added)
        self._last_refill[platform] = now

    async def acquire(self, platform: str) -> None:
        cfg = self._limits.get(platform, self._DEFAULT)
        async with self._locks[platform]:
            self._refill(platform)
            if self._tokens[platform] < 1:
                wait = (1 - self._tokens[platform]) * (cfg["period"] / cfg["rate"])
                await asyncio.sleep(wait)
                self._refill(platform)
            self._tokens[platform] -= 1
