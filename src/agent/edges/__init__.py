"""
src/agent/edges/conditions.py
-------------------------------
Conditional edge routing functions — Zepto + Blinkit.
"""
from __future__ import annotations
from src.agent.state import AgentState


def route_after_parser(state: AgentState) -> str:
    if state.get("is_valid_query"):
        return "cache_check"
    return "error_handler"


def route_after_cache(state: AgentState):
    """Cache hit → response_router | Cache miss → parallel scrapers (list)."""
    if state.get("cache_hit"):
        return "response_router"
    return ["scraper_zepto", "scraper_blinkit"]


def route_after_aggregation(state: AgentState) -> str:
    if state.get("price_comparison") is not None:
        return "response_router"
    return "error_handler"
