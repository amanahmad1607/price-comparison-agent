"""
src/infrastructure/http_client.py
-----------------------------------
Async HTTP/2 client with tenacity retry and exponential backoff.
"""
from __future__ import annotations
import logging
import httpx
from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type, before_sleep_log,
)

logger = logging.getLogger(__name__)
_RETRYABLE = (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError)


class AsyncHTTPClient:
    def __init__(self, base_url: str, headers: dict | None = None,
                 timeout: float = 10.0, connect_timeout: float = 3.0,
                 max_retries: int = 3):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers=headers or {},
            timeout=httpx.Timeout(timeout, connect=connect_timeout),
            follow_redirects=True,
            http2=True,
        )
        self._max_retries = max_retries

    def _retry(self):
        return retry(
            stop=stop_after_attempt(self._max_retries),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type(_RETRYABLE),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            reraise=True,
        )

    async def get(self, path: str, **kwargs) -> httpx.Response:
        @self._retry()
        async def _get():
            resp = await self._client.get(path, **kwargs)
            resp.raise_for_status()
            return resp
        return await _get()

    async def post(self, path: str, **kwargs) -> httpx.Response:
        @self._retry()
        async def _post():
            resp = await self._client.post(path, **kwargs)
            resp.raise_for_status()
            return resp
        return await _post()

    async def close(self) -> None:
        await self._client.aclose()
