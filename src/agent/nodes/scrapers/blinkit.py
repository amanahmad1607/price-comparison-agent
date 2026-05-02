"""
src/agent/nodes/scrapers/blinkit.py
--------------------------------------
Blinkit Playwright scraper.
Intercepts: blinkit.com/v1/layout/search
Response structure: response.snippets[].data → name.text, normal_price.text, mrp.text, variant.text
Prices are strings like "₹74" — strip ₹ and parse.
"""
from __future__ import annotations
import re
from typing import Optional
from datetime import datetime, timezone

from src.agent.nodes.scrapers.base import BaseScraper
from src.agent.nodes.scrapers.base_playwright import new_page
from src.models.product import PlatformResult, RawProduct


def _parse_price(text: str) -> float:
    """Extract float from '₹74' or '₹1,234' strings."""
    if not text:
        return 0.0
    cleaned = re.sub(r"[^\d.]", "", text.replace(",", ""))
    try:
        return float(cleaned)
    except Exception:
        return 0.0


class BlinkitScraper(BaseScraper):
    PLATFORM = "blinkit"
    BASE_URL  = "https://blinkit.com"

    async def search(self, product: str, brand: Optional[str], pincode: Optional[str]) -> PlatformResult:
        query    = f"{brand} {product}".strip() if brand else product
        captured = []

        try:
            page = await new_page()

            async def intercept(response):
                if "blinkit.com/v1/layout/search" in response.url and response.status == 200:
                    try:
                        captured.append(await response.json())
                    except Exception:
                        pass

            page.on("response", intercept)
            await page.goto(
                f"https://blinkit.com/s/?q={query}",
                wait_until="networkidle", timeout=30000,
            )
            await page.wait_for_timeout(3000)
            await page.close()

            if not captured:
                return self._error("No v1/layout/search response captured")

            products = []
            seen_ids = set()

            for data in captured:
                snippets = data.get("response", {}).get("snippets", [])
                for snippet in snippets:
                    d = snippet.get("data", {})

                    # Product ID from identity
                    product_id = str(d.get("identity", {}).get("id", ""))
                    if not product_id or product_id in seen_ids:
                        continue
                    seen_ids.add(product_id)

                    # Name from data.name.text
                    name = d.get("name", {}).get("text", "")
                    if not name:
                        continue

                    # Prices from data.normal_price.text and data.mrp.text
                    price = _parse_price(d.get("normal_price", {}).get("text", ""))
                    mrp   = _parse_price(d.get("mrp", {}).get("text", ""))

                    # Fallback to tracking click_map
                    if price == 0 and mrp == 0:
                        cm    = snippet.get("tracking", {}).get("click_map", {})
                        price = float(cm.get("price", 0) or 0)
                        mrp   = float(cm.get("mrp", 0) or 0)

                    if price == 0:
                        price = mrp

                    qty_str    = d.get("variant", {}).get("text", "1 piece")
                    img_url    = d.get("image", {}).get("url")
                    brand_name = snippet.get("tracking", {}).get("click_map", {}).get("brand")
                    in_stock   = int(d.get("inventory", 1)) > 0

                    products.append(RawProduct(
                        platform=self.PLATFORM,
                        product_id=product_id,
                        name=name,
                        brand=brand_name,
                        image_url=img_url,
                        mrp=mrp,
                        selling_price=price,
                        discount_pct=self._discount(mrp, price),
                        quantity_str=qty_str,
                        in_stock=in_stock,
                        delivery_time_min=None,
                        product_url=f"https://blinkit.com/s/?q={name.replace(' ', '+')}",
                        scraped_at=self._now(),
                    ))

            return self._success(products) if products else self._error("0 products from snippets")

        except Exception as e:
            return self._error(str(e))
