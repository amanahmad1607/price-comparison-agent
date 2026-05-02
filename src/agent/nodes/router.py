"""src/agent/nodes/router.py — response router node."""
from __future__ import annotations
import asyncio, time, logging
from src.agent.state import AgentState

logger = logging.getLogger(__name__)


async def response_router_node(state: AgentState) -> dict:
    t0         = time.perf_counter()
    comparison = state.get("price_comparison") or state.get("cached_result")
    asyncio.create_task(_emit_analytics(state, comparison))
    return {
        "price_comparison": comparison,
        "should_alert": False,
        "node_timings": {"response_router": (time.perf_counter() - t0) * 1000},
    }


async def _emit_analytics(state, comparison) -> None:
    try:
        logger.info(
            "analytics cheapest=%s platforms=%d cache_hit=%s",
            comparison.cheapest_platform if comparison else None,
            len(comparison.platforms_with_results) if comparison else 0,
            state.get("cache_hit", False),
        )
    except Exception:
        pass
