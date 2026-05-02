"""
src/agent/nodes/normalizer.py
-------------------------------
NODE: normalizer — unit/weight disambiguation and price-per-unit calculation.
"""
from __future__ import annotations
import re, time, logging
from src.agent.state import AgentState
from src.models.product import NormalizedProduct

logger = logging.getLogger(__name__)

_QTY_RE = re.compile(
    r"(\d+(?:\.\d+)?)\s*[xX×]?\s*(\d+(?:\.\d+)?)?\s*"
    r"(ml|l|litre|liter|g|gm|gram|grams|kg|kilogram|pack|pcs|piece|pieces)?",
    re.IGNORECASE,
)
_UNIT_MAP = {
    "ml":"ml","l":"L","litre":"L","liter":"L",
    "g":"g","gm":"g","gram":"g","grams":"g",
    "kg":"kg","kilogram":"kg",
    "pack":"pack","pcs":"piece","piece":"piece","pieces":"piece",
}


def _parse_quantity(qty_str: str) -> tuple[float, str]:
    if not qty_str:
        return 1.0, "piece"
    m = _QTY_RE.search(qty_str)
    if not m:
        return 1.0, "piece"
    count      = float(m.group(1) or 1)
    multiplier = float(m.group(2) or 0)
    raw_unit   = (m.group(3) or "piece").lower()
    unit       = _UNIT_MAP.get(raw_unit, "piece")
    total      = count * multiplier if multiplier else count
    if unit == "kg":
        total *= 1000; unit = "g"
    elif unit == "L":
        total *= 1000; unit = "ml"
    return total, unit


async def normalizer_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    normalised = []
    for pr in state["platform_results"]:
        if pr.error:
            continue
        for raw in pr.products:
            try:
                qty_val, qty_unit = _parse_quantity(raw.quantity_str)
                ppu = raw.selling_price / qty_val if qty_val > 0 else raw.selling_price
                normalised.append(NormalizedProduct(
                    platform=raw.platform,
                    product_id=raw.product_id,
                    name=raw.name,
                    brand=raw.brand,
                    image_url=raw.image_url,
                    mrp=raw.mrp,
                    selling_price=raw.selling_price,
                    discount_pct=raw.discount_pct,
                    quantity_value=qty_val,
                    quantity_unit=qty_unit,
                    price_per_unit=round(ppu, 4),
                    price_per_unit_label=f"₹{ppu:.3f}/{qty_unit}" if ppu < 1 else f"₹{ppu:.2f}/{qty_unit}",
                    in_stock=raw.in_stock,
                    delivery_time_min=raw.delivery_time_min,
                    product_url=raw.product_url,
                    scraped_at=raw.scraped_at,
                ))
            except Exception as e:
                logger.warning("normalizer skip %s/%s err=%s", raw.platform, raw.product_id, e)
    return {
        "normalized_products": normalised,
        "node_timings": {"normalizer": (time.perf_counter() - t0) * 1000},
    }
