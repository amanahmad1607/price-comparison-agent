"""tests/unit/test_aggregator.py — badge assignment and ranking."""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch
from src.agent.nodes.aggregator import aggregator_node, _assign_badges
from src.agent.state import initial_state
from src.models.product import NormalizedProduct, PlatformSummary
from src.models.query import ParsedQuery


def _now():
    return datetime.now(timezone.utc)


def make_product(platform, price, ppu, delivery=20, in_stock=True) -> NormalizedProduct:
    return NormalizedProduct(
        platform=platform, product_id=f"{platform}-001",
        name=f"{platform} product", brand="Brand",
        mrp=price + 5, selling_price=price, discount_pct=10.0,
        quantity_value=70.0, quantity_unit="g",
        price_per_unit=ppu, price_per_unit_label=f"₹{ppu:.3f}/g",
        in_stock=in_stock, delivery_time_min=delivery,
        product_url=f"https://{platform}.com/p", scraped_at=_now(),
    )


def make_state(products):
    s = initial_state(raw_query="Maggi 70g", session_id="t")
    s["parsed_query"] = ParsedQuery(
        product_name="noodles", brand="Maggi", quantity=70, unit="g",
        platforms=["zepto", "blinkit"], raw="Maggi 70g",
    )
    s["normalized_products"] = products
    s["cache_key"] = "test-key"
    return s


class TestAssignBadges:
    def test_cheapest_badge(self):
        sums = [
            PlatformSummary(platform="zepto", best_price=13.0, best_product_name="",
                best_product_url="", discount_pct=10, price_per_unit=0.186,
                price_per_unit_label="", in_stock=True, delivery_time_min=12),
            PlatformSummary(platform="blinkit", best_price=20.0, best_product_name="",
                best_product_url="", discount_pct=5, price_per_unit=0.150,
                price_per_unit_label="", in_stock=True, delivery_time_min=8),
        ]
        _assign_badges(sums)
        assert next(s for s in sums if s.platform == "zepto").badge == "Cheapest"

    def test_fastest_badge(self):
        sums = [
            PlatformSummary(platform="zepto", best_price=13.0, best_product_name="",
                best_product_url="", discount_pct=10, price_per_unit=0.186,
                price_per_unit_label="", in_stock=True, delivery_time_min=20),
            PlatformSummary(platform="blinkit", best_price=15.0, best_product_name="",
                best_product_url="", discount_pct=5, price_per_unit=0.214,
                price_per_unit_label="", in_stock=True, delivery_time_min=8),
        ]
        _assign_badges(sums)
        assert next(s for s in sums if s.platform == "blinkit").badge == "Fastest delivery"


@pytest.mark.asyncio
async def test_aggregator_cheapest():
    prods = [make_product("zepto", 13.0, 0.186), make_product("blinkit", 20.0, 0.286)]
    with patch("src.agent.nodes.aggregator._cache", new=None):
        result = await aggregator_node(make_state(prods))
    assert result["price_comparison"].cheapest_platform == "zepto"


@pytest.mark.asyncio
async def test_aggregator_no_products():
    with patch("src.agent.nodes.aggregator._cache", new=None):
        result = await aggregator_node(make_state([]))
    assert result["price_comparison"] is None


@pytest.mark.asyncio
async def test_aggregator_excludes_out_of_stock():
    prods = [
        make_product("zepto", 13.0, 0.186, in_stock=False),
        make_product("blinkit", 20.0, 0.286, in_stock=True),
    ]
    with patch("src.agent.nodes.aggregator._cache", new=None):
        result = await aggregator_node(make_state(prods))
    comp = result["price_comparison"]
    assert len(comp.platform_summaries) == 1
    assert comp.cheapest_platform == "blinkit"
