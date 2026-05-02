"""tests/unit/test_normalizer.py — quantity parsing + price-per-unit."""
import pytest
from datetime import datetime, timezone
from src.agent.nodes.normalizer import normalizer_node
from src.agent.state import initial_state
from src.models.product import PlatformResult, RawProduct


def _now():
    return datetime.now(timezone.utc)


def make_raw(platform: str, qty_str: str, price: float = 50.0) -> RawProduct:
    return RawProduct(
        platform=platform, product_id="t-001", name="Test Product",
        brand="Brand", mrp=60.0, selling_price=price, discount_pct=10.0,
        quantity_str=qty_str, in_stock=True, delivery_time_min=15,
        product_url=f"https://{platform}.com/p", scraped_at=_now(),
    )


@pytest.mark.asyncio
async def test_normalizer_500ml():
    state = initial_state(raw_query="milk", session_id="t")
    state["platform_results"] = [
        PlatformResult(platform="zepto", products=[make_raw("zepto", "500 ml", 30.0)])
    ]
    result = await normalizer_node(state)
    p = result["normalized_products"][0]
    assert p.quantity_value == 500.0
    assert p.quantity_unit == "ml"
    assert abs(p.price_per_unit - 30.0 / 500.0) < 0.001


@pytest.mark.asyncio
async def test_normalizer_1kg_converts_to_grams():
    state = initial_state(raw_query="salt", session_id="t")
    state["platform_results"] = [
        PlatformResult(platform="blinkit", products=[make_raw("blinkit", "1 kg", 20.0)])
    ]
    result = await normalizer_node(state)
    p = result["normalized_products"][0]
    assert p.quantity_value == 1000.0
    assert p.quantity_unit == "g"


@pytest.mark.asyncio
async def test_normalizer_skips_error_platforms():
    state = initial_state(raw_query="milk", session_id="t")
    state["platform_results"] = [
        PlatformResult(platform="zepto", products=[], error="timeout"),
        PlatformResult(platform="blinkit", products=[make_raw("blinkit", "70 g", 14.0)]),
    ]
    result = await normalizer_node(state)
    assert len(result["normalized_products"]) == 1
    assert result["normalized_products"][0].platform == "blinkit"


@pytest.mark.asyncio
async def test_normalizer_empty():
    state = initial_state(raw_query="milk", session_id="t")
    state["platform_results"] = []
    result = await normalizer_node(state)
    assert result["normalized_products"] == []
