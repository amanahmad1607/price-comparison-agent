"""
src/infrastructure/cache.py
----------------------------
Async Redis client — failure-safe (errors never crash the agent).
"""
from __future__ import annotations
import logging
from typing import Optional
import redis.asyncio as aioredis

logger = logging.getLogger(__name__)


class RedisCache:
    def __init__(self, url: str, max_connections: int = 50):
        self._pool = aioredis.ConnectionPool.from_url(
            url, max_connections=max_connections, decode_responses=True,
        )
        self._redis = aioredis.Redis(connection_pool=self._pool)

    async def get(self, key: str) -> Optional[str]:
        try:
            return await self._redis.get(key)
        except Exception as e:
            logger.warning("cache.get failed key=%s err=%s", key, e)
            return None

    async def set(self, key: str, value: str, ttl: int = 300) -> bool:
        try:
            await self._redis.set(key, value, ex=ttl)
            return True
        except Exception as e:
            logger.warning("cache.set failed key=%s err=%s", key, e)
            return False

    async def delete(self, key: str) -> None:
        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.warning("cache.delete failed key=%s err=%s", key, e)

    async def ping(self) -> bool:
        try:
            return await self._redis.ping()
        except Exception:
            return False

    async def close(self) -> None:
        try:
            await self._redis.aclose()
        except Exception:
            pass
