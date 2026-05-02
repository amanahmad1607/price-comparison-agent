"""src/agent/nodes/error_handler.py — error handler node."""
from __future__ import annotations
import time, logging
from src.agent.state import AgentState

logger = logging.getLogger(__name__)


async def error_handler_node(state: AgentState) -> dict:
    t0 = time.perf_counter()

    error_msg = state.get("error_message")
    if not error_msg:
        errs = state.get("validation_errors", [])
        if errs:
            error_msg = "; ".join(errs)
        elif not state.get("is_valid_query"):
            error_msg = "Could not understand your query. Please try again with more detail."
        else:
            failed = [
                s["platform"] for s in state.get("scraper_statuses", [])
                if s["status"] != "success"
            ]
            error_msg = (
                f"No results found. Platforms that didn't respond: {', '.join(failed)}."
                if failed else "No products found matching your query."
            )

    logger.error("agent.error session=%s query=%r msg=%s",
                 state.get("session_id"), state.get("raw_query"), error_msg)

    return {
        "error_message": error_msg,
        "price_comparison": None,
        "node_timings": {"error_handler": (time.perf_counter() - t0) * 1000},
    }
