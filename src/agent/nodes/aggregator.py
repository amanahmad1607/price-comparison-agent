"""
src/agent/nodes/aggregator.py
-------------------------------
NODE: aggregator — ranking, badge assignment, cache write.
"""
from __future__ import annotations
import asyncio, time, logging
from datetime import datetime, timezone
from src.agent.state import AgentState
from src.models.product import NormalizedProduct, PlatformSummary, PriceComparison

logger = logging.getLogger(__name__)
_cache = None


def set_cache(cache) -> None:
    global _cache
    _cache = cache


def _assign_badges(summaries: list[PlatformSummary]) -> None:
    in_stock = [s for s in summaries if s.in_stock]
    if not in_stock:
        return
    cheapest = min(in_stock, key=lambda s: s.best_price)
    cheapest.badge = "Cheapest"
    timed   = [s for s in in_stock if s.delivery_time_min is not None]
    fastest = min(timed, key=lambda s: s.delivery_time_min) if timed else None
    if fastest is not None and fastest is not cheapest:
        fastest.badge = "Fastest delivery"
    best_value = min(in_stock, key=lambda s: s.price_per_unit)
    already    = [x for x in [cheapest, fastest] if x is not None]
    if best_value not in already:
        best_value.badge = "Best value"


async def aggregator_node(state: AgentState) -> dict:
    t0       = time.perf_counter()
    pq       = state["parsed_query"]
    in_stock = [p for p in state["normalized_products"] if p.in_stock]

    if not in_stock:
        logger.warning("aggregator: no in-stock products found")
        return {
            "price_comparison": None,
            "node_timings": {"aggregator": (time.perf_counter() - t0) * 1000},
        }

    by_platform: dict[str, list[NormalizedProduct]] = {}
    for p in in_stock:
        by_platform.setdefault(p.platform, []).append(p)

    summaries = []
    for platform, prods in by_platform.items():
        best       = min(prods, key=lambda x: x.selling_price)
        best_value = min(prods, key=lambda x: x.price_per_unit)
        summaries.append(PlatformSummary(
            platform=platform,
            best_price=best.selling_price,
            best_product_name=best.name,
            best_product_url=best.product_url,
            discount_pct=best.discount_pct,
            price_per_unit=best_value.price_per_unit,
            price_per_unit_label=best_value.price_per_unit_label,
            in_stock=True,
            delivery_time_min=best.delivery_time_min,
            badge=None,
        ))

    _assign_badges(summaries)

    cheapest   = min(summaries, key=lambda s: s.best_price)
    timed      = [s for s in summaries if s.delivery_time_min is not None]
    fastest    = min(timed, key=lambda s: s.delivery_time_min) if timed else None
    best_value = min(summaries, key=lambda s: s.price_per_unit)

    comparison = PriceComparison(
        query=pq.raw,
        platforms_searched=pq.platforms,
        platforms_with_results=list(by_platform.keys()),
        platform_summaries=sorted(summaries, key=lambda s: s.best_price),
        cheapest_platform=cheapest.platform,
        fastest_delivery_platform=fastest.platform if fastest else None,
        best_value_platform=best_value.platform,
        all_products=sorted(in_stock, key=lambda p: p.selling_price),
        generated_at=datetime.now(timezone.utc),
        cache_key=state.get("cache_key"),
    )

    if state.get("cache_key") and _cache:
        asyncio.create_task(_cache.set(state["cache_key"], comparison.model_dump_json(), ttl=300))

    return {
        "price_comparison": comparison,
        "node_timings": {"aggregator": (time.perf_counter() - t0) * 1000},
    }
