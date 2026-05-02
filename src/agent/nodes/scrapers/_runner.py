"""
src/agent/nodes/scrapers/_runner.py
--------------------------------------
LangGraph node functions for Zepto and Blinkit.
Patched at _run_platform level for testability.
"""
from __future__ import annotations
import asyncio, time, logging
from src.agent.state import AgentState, ScraperStatus
from src.agent.nodes.scrapers.zepto import ZeptoScraper
from src.agent.nodes.scrapers.blinkit import BlinkitScraper
from src.models.product import PlatformResult

logger = logging.getLogger(__name__)

_rate_limiter = None
TIMEOUT_SECS  = 30
MAX_RETRIES   = 2

SCRAPER_CLASSES = {
    "zepto":   ZeptoScraper,
    "blinkit": BlinkitScraper,
}


def set_rate_limiter(limiter) -> None:
    global _rate_limiter
    _rate_limiter = limiter


async def _run_platform(platform: str, state: AgentState) -> dict:
    pq = state["parsed_query"]
    if platform not in pq.platforms:
        return {"platform_results": [], "scraper_statuses": []}

    t0      = time.perf_counter()
    scraper = SCRAPER_CLASSES[platform]()

    if _rate_limiter:
        await _rate_limiter.acquire(platform)

    last_error = "unknown"
    for attempt in range(MAX_RETRIES + 1):
        try:
            result: PlatformResult = await asyncio.wait_for(
                scraper.search(
                    product=pq.product_name,
                    brand=pq.brand,
                    pincode=state.get("location_pincode"),
                ),
                timeout=TIMEOUT_SECS,
            )
            latency = (time.perf_counter() - t0) * 1000
            result.latency_ms = latency
            logger.info("scraper.success platform=%s products=%d latency_ms=%.0f",
                        platform, len(result.products), latency)
            return {
                "platform_results":  [result],
                "scraper_statuses":  [ScraperStatus(
                    platform=platform, status="success",
                    error=None, latency_ms=latency,
                    products_found=len(result.products),
                )],
                "node_timings": {f"scraper_{platform}": latency},
            }
        except asyncio.TimeoutError:
            last_error = f"timeout after {TIMEOUT_SECS}s"
        except Exception as exc:
            last_error = str(exc)

        if attempt < MAX_RETRIES:
            await asyncio.sleep(2 ** attempt)

    latency  = (time.perf_counter() - t0) * 1000
    status_v = "timeout" if "timeout" in last_error else "failed"
    return {
        "platform_results":  [PlatformResult(platform=platform, products=[], error=last_error)],
        "scraper_statuses":  [ScraperStatus(
            platform=platform, status=status_v,
            error=last_error, latency_ms=latency, products_found=0,
        )],
        "node_timings": {f"scraper_{platform}": latency},
    }


async def scraper_zepto_node(state: AgentState) -> dict:
    return await _run_platform("zepto", state)


async def scraper_blinkit_node(state: AgentState) -> dict:
    return await _run_platform("blinkit", state)
