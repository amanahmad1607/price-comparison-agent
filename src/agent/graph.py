"""
src/agent/graph.py
------------------
LangGraph StateGraph — Zepto + Blinkit only.

Topology:
START → query_parser
         ├─[invalid]─► error_handler → END
         └─[valid]──► cache_check
               ├─[hit]──► response_router → END
               └─[miss]─► scraper_zepto ┐  (parallel)
                           scraper_blinkit ┘
                                └─► normalizer → aggregator
                                     ├─[results]──► response_router → END
                                     └─[empty]───► error_handler → END
"""
from __future__ import annotations
import os, logging
from functools import lru_cache

from langgraph.graph import StateGraph, START, END
from langchain_groq import ChatGroq

from src.agent.state import AgentState
from src.agent.edges.conditions import route_after_parser, route_after_cache, route_after_aggregation
from src.agent.nodes.query_parser import query_parser_node, set_llm
from src.agent.nodes.cache_check import cache_check_node, set_cache as cache_set_cache
from src.agent.nodes.scrapers._runner import (
    scraper_zepto_node, scraper_blinkit_node, set_rate_limiter,
)
from src.agent.nodes.normalizer import normalizer_node
from src.agent.nodes.aggregator import aggregator_node, set_cache as agg_set_cache
from src.agent.nodes.router import response_router_node
from src.agent.nodes.error_handler import error_handler_node
from src.infrastructure.cache import RedisCache
from src.infrastructure.rate_limiter import RateLimiter
from src.infrastructure.observability import with_tracing

logger = logging.getLogger(__name__)


def build_graph(checkpointer=None):
    """Compile the LangGraph price-comparison graph."""
    builder = StateGraph(AgentState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    builder.add_node("query_parser",    with_tracing(query_parser_node))
    builder.add_node("cache_check",     with_tracing(cache_check_node))
    builder.add_node("scraper_zepto",   with_tracing(scraper_zepto_node))
    builder.add_node("scraper_blinkit", with_tracing(scraper_blinkit_node))
    builder.add_node("normalizer",      with_tracing(normalizer_node))
    builder.add_node("aggregator",      with_tracing(aggregator_node))
    builder.add_node("response_router", with_tracing(response_router_node))
    builder.add_node("error_handler",   with_tracing(error_handler_node))

    # ── Edges ──────────────────────────────────────────────────────────────────
    builder.add_edge(START, "query_parser")

    builder.add_conditional_edges(
        "query_parser", route_after_parser,
        {"cache_check": "cache_check", "error_handler": "error_handler"},
    )

    # route_after_cache returns a list on cache miss → parallel fan-out
    builder.add_conditional_edges(
        "cache_check", route_after_cache,
        {
            "response_router": "response_router",
            "scraper_zepto":   "scraper_zepto",
            "scraper_blinkit": "scraper_blinkit",
        },
    )

    # Fan-in: both scrapers → normalizer
    builder.add_edge("scraper_zepto",   "normalizer")
    builder.add_edge("scraper_blinkit", "normalizer")
    builder.add_edge("normalizer",      "aggregator")

    builder.add_conditional_edges(
        "aggregator", route_after_aggregation,
        {"response_router": "response_router", "error_handler": "error_handler"},
    )

    builder.add_edge("response_router", END)
    builder.add_edge("error_handler",   END)

    return builder.compile(checkpointer=checkpointer)


@lru_cache(maxsize=1)
def create_agent():
    """Singleton factory — called once at FastAPI startup."""
    llm = ChatGroq(
        model="llama-3.1-8b-instant",
        temperature=0,
        api_key=os.environ["GROQ_API_KEY"],
    )

    cache = RedisCache(
        url=os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
        max_connections=50,
    )

    rate_limiter = RateLimiter(limits={
        "zepto":   {"rate": int(os.environ.get("ZEPTO_RATE_LIMIT", 10)),   "period": 60},
        "blinkit": {"rate": int(os.environ.get("BLINKIT_RATE_LIMIT", 10)), "period": 60},
    })

    set_llm(llm)
    cache_set_cache(cache)
    agg_set_cache(cache)
    set_rate_limiter(rate_limiter)

    logger.info("agent: building graph (zepto + blinkit)")
    return build_graph()
