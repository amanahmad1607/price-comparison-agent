"""
tests/integration/test_agent.py
---------------------------------
Full graph integration tests — Zepto + Blinkit only.
Uses mocked _run_platform + fakeredis. No real network calls.
"""
import json, pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.agent.graph import build_graph
from src.agent.state import initial_state
from src.agent.nodes.query_parser import set_llm
from src.agent.nodes.scrapers._runner import set_rate_limiter
from src.agent.nodes.cache_check import set_cache as cache_set_cache
from src.agent.nodes.aggregator import set_cache as agg_set_cache
from src.infrastructure.rate_limiter import RateLimiter
from src.models.product import PlatformResult, RawProduct, PriceComparison


def _now():
    return datetime.now(timezone.utc)


def make_product(platform: str, price: float) -> RawProduct:
    return RawProduct(
        platform=platform, product_id=f"{platform}-p1",
        name=f"Maggi Masala Noodles 70g", brand="Maggi",
        mrp=price + 5, selling_price=price,
        discount_pct=round(5 / (price + 5) * 100, 1),
        quantity_str="70 g", in_stock=True,
        delivery_time_min=12,
        product_url=f"https://{platform}.com/p",
        scraped_at=_now(),
    )


MOCK_RESULTS = {
    "zepto":   PlatformResult(platform="zepto",   products=[make_product("zepto",   13.0)]),
    "blinkit": PlatformResult(platform="blinkit", products=[make_product("blinkit", 20.0)]),
}


@pytest.fixture
def fake_cache():
    import fakeredis.aioredis
    from src.infrastructure.cache import RedisCache
    r = fakeredis.aioredis.FakeRedis(decode_responses=True)
    c = RedisCache.__new__(RedisCache)
    c._redis = r
    return c


@pytest.fixture(autouse=True)
def setup_deps(fake_cache):
    llm = AsyncMock()
    msg = MagicMock()
    msg.content = json.dumps({
        "product_name": "noodles", "brand": "Maggi",
        "quantity": 70, "unit": "g", "category": "snacks",
        "max_price": None, "platforms": [],
    })
    llm.ainvoke = AsyncMock(return_value=msg)
    set_llm(llm)
    cache_set_cache(fake_cache)
    agg_set_cache(fake_cache)
    set_rate_limiter(RateLimiter(
        limits={p: {"rate": 1000, "period": 1} for p in ["zepto", "blinkit"]}
    ))


def _mock_runner(results=MOCK_RESULTS, fail_platforms=None):
    fail_platforms = fail_platforms or []

    async def _run(platform, state):
        if platform not in state["parsed_query"].platforms:
            return {"platform_results": [], "scraper_statuses": []}
        if platform in fail_platforms:
            return {
                "platform_results": [PlatformResult(platform=platform, products=[], error="timeout")],
                "scraper_statuses": [{"platform": platform, "status": "failed",
                                      "error": "timeout", "latency_ms": 30000.0, "products_found": 0}],
                "node_timings": {f"scraper_{platform}": 30000.0},
            }
        r = results.get(platform, PlatformResult(platform=platform, products=[]))
        return {
            "platform_results": [r],
            "scraper_statuses": [{"platform": platform, "status": "success",
                                  "error": None, "latency_ms": 120.0,
                                  "products_found": len(r.products)}],
            "node_timings": {f"scraper_{platform}": 120.0},
        }
    return _run


@pytest.mark.asyncio
async def test_happy_path(setup_deps):
    with patch("src.agent.nodes.scrapers._runner._run_platform", new=_mock_runner()):
        result = await build_graph().ainvoke(
            initial_state(raw_query="Maggi 70g", session_id="t-001")
        )
    comp = result.get("price_comparison")
    assert comp is not None
    assert len(comp.platform_summaries) == 2
    assert comp.cheapest_platform == "zepto"


@pytest.mark.asyncio
async def test_invalid_query(setup_deps):
    result = await build_graph().ainvoke(
        initial_state(raw_query="ab", session_id="t-002")
    )
    assert result["is_valid_query"] is False
    assert result["price_comparison"] is None


@pytest.mark.asyncio
async def test_cache_hit_skips_scrapers(setup_deps):
    cached = PriceComparison(
        query="Maggi 70g", platforms_searched=["zepto", "blinkit"],
        platforms_with_results=["zepto"], platform_summaries=[],
        cheapest_platform="zepto", fastest_delivery_platform=None,
        best_value_platform="zepto", all_products=[],
    )
    called = {"v": False}

    async def spy(platform, state):
        called["v"] = True
        return {"platform_results": [], "scraper_statuses": []}

    with (
        patch("src.agent.nodes.scrapers._runner._run_platform", new=spy),
        patch("src.agent.nodes.cache_check._cache") as mc,
    ):
        mc.get = AsyncMock(return_value=cached.model_dump_json())
        result = await build_graph().ainvoke(
            initial_state(raw_query="Maggi 70g", session_id="t-003")
        )
    assert called["v"] is False
    assert result.get("cache_hit") is True


@pytest.mark.asyncio
async def test_one_scraper_fails(setup_deps):
    with patch("src.agent.nodes.scrapers._runner._run_platform",
               new=_mock_runner(fail_platforms=["blinkit"])):
        result = await build_graph().ainvoke(
            initial_state(raw_query="Maggi 70g", session_id="t-004")
        )
    comp = result.get("price_comparison")
    assert comp is not None
    assert len(comp.platform_summaries) == 1
    assert comp.platform_summaries[0].platform == "zepto"


@pytest.mark.asyncio
async def test_all_scrapers_fail(setup_deps):
    with patch("src.agent.nodes.scrapers._runner._run_platform",
               new=_mock_runner(fail_platforms=["zepto", "blinkit"])):
        result = await build_graph().ainvoke(
            initial_state(raw_query="Maggi 70g", session_id="t-005")
        )
    assert result.get("price_comparison") is None
    assert result.get("error_message") is not None
