"""
src/agent/nodes/cache_check.py
--------------------------------
NODE: cache_check — Redis cache lookup with content-addressed key.
"""
from __future__ import annotations
import hashlib, time, logging
from src.agent.state import AgentState
from src.models.product import PriceComparison

logger = logging.getLogger(__name__)
_cache = None


def set_cache(cache) -> None:
    global _cache
    _cache = cache


def _build_cache_key(state: AgentState) -> str:
    pq = state["parsed_query"]
    raw = "|".join([
        (pq.product_name or "").lower(),
        (pq.brand or "").lower(),
        str(pq.quantity or ""),
        (pq.unit or "").lower(),
        (state["location_pincode"] or ""),
        "_".join(sorted(pq.platforms)),
    ])
    digest = hashlib.sha256(raw.encode()).hexdigest()[:24]
    return f"pca:v1:{digest}"


async def cache_check_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    key = _build_cache_key(state)
    cached_json = await _cache.get(key)

    if cached_json:
        try:
            result = PriceComparison.model_validate_json(cached_json)
            return {
                "cache_key": key,
                "cache_hit": True,
                "cached_result": result,
                "node_timings": {"cache_check": (time.perf_counter() - t0) * 1000},
            }
        except Exception as e:
            logger.warning("cache corrupt key=%s err=%s", key, e)
            await _cache.delete(key)

    return {
        "cache_key": key,
        "cache_hit": False,
        "node_timings": {"cache_check": (time.perf_counter() - t0) * 1000},
    }
