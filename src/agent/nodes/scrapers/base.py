"""
src/agent/nodes/scrapers/base.py
----------------------------------
Abstract base scraper shared by Zepto and Blinkit.
"""
from __future__ import annotations
import abc
from datetime import datetime, timezone
from typing import Optional
from src.infrastructure.http_client import AsyncHTTPClient
from src.models.product import PlatformResult, RawProduct


class BaseScraper(abc.ABC):
    PLATFORM: str
    BASE_URL: str
    HEADERS: dict = {}
    _UA = (
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Mobile Safari/537.36"
    )

    def __init__(self):
        self.client = AsyncHTTPClient(
            base_url=self.BASE_URL,
            headers={"User-Agent": self._UA, **self.HEADERS},
        )

    @abc.abstractmethod
    async def search(self, product: str, brand: Optional[str], pincode: Optional[str]) -> PlatformResult:
        pass

    def _success(self, products: list[RawProduct]) -> PlatformResult:
        return PlatformResult(platform=self.PLATFORM, products=products)

    def _error(self, error: str) -> PlatformResult:
        return PlatformResult(platform=self.PLATFORM, products=[], error=error)

    @staticmethod
    def _discount(mrp: float, price: float) -> float:
        if mrp <= 0 or price >= mrp:
            return 0.0
        return round((mrp - price) / mrp * 100, 1)

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def close(self) -> None:
        await self.client.close()
