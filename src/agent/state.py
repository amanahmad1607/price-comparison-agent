"""
src/agent/state.py
------------------
Central AgentState TypedDict — Zepto + Blinkit only.
"""
from __future__ import annotations
import time
from typing import Literal, Optional
from typing_extensions import TypedDict, Annotated
import operator
from src.models.query import ParsedQuery
from src.models.product import PlatformResult, NormalizedProduct, PriceComparison

PLATFORMS = ["zepto", "blinkit"]


class ScraperStatus(TypedDict):
    platform: str
    status: Literal["pending", "success", "failed", "timeout"]
    error: Optional[str]
    latency_ms: Optional[float]
    products_found: int


class AgentState(TypedDict):
    # Input
    raw_query: str
    user_id: Optional[str]
    session_id: str
    location_pincode: Optional[str]
    platform_filter: list[str]
    channel: Literal["api", "web", "cli"]

    # Parsed
    parsed_query: Optional[ParsedQuery]
    is_valid_query: bool
    validation_errors: list[str]

    # Cache
    cache_key: Optional[str]
    cache_hit: bool
    cached_result: Optional[PriceComparison]

    # Scraper outputs — operator.add so parallel branches MERGE
    platform_results: Annotated[list[PlatformResult], operator.add]
    scraper_statuses: Annotated[list[ScraperStatus], operator.add]

    # Processing
    normalized_products: list[NormalizedProduct]
    price_comparison: Optional[PriceComparison]

    # Control
    retry_count: int
    error_message: Optional[str]
    should_alert: bool

    # Observability
    trace_id: str
    start_ts: float
    node_timings: Annotated[dict[str, float], operator.or_]


def initial_state(
    raw_query: str,
    session_id: str,
    user_id: str | None = None,
    pincode: str | None = None,
    platform_filter: list[str] | None = None,
    channel: str = "api",
) -> AgentState:
    return AgentState(
        raw_query=raw_query,
        user_id=user_id,
        session_id=session_id,
        location_pincode=pincode,
        platform_filter=platform_filter or [],
        channel=channel,
        parsed_query=None,
        is_valid_query=False,
        validation_errors=[],
        cache_key=None,
        cache_hit=False,
        cached_result=None,
        platform_results=[],
        scraper_statuses=[],
        normalized_products=[],
        price_comparison=None,
        retry_count=0,
        error_message=None,
        should_alert=False,
        trace_id="",
        start_ts=time.time(),
        node_timings={},
    )
