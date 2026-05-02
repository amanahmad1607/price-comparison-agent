"""
src/agent/nodes/scrapers/zepto.py
-----------------------------------
Zepto Playwright scraper.

Confirmed working API: bff-gateway.zepto.com/user-search-service/api/v3/search
Response: layout[] → widgetId == "PRODUCT_GRID" → items[].productResponse
Prices are in PAISE — divide by 100 for INR.
price field is a dict — use discountedSellingPrice or sellingPrice instead.
"""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from src.models.product import PlatformResult, RawProduct

IMAGE_BASE = "https://cdn.zeptonow.com/production/tr:w-640,ar-1-1,dpr-1,pr-true,f-auto/cms/"


class ZeptoScraper:
    PLATFORM = "zepto"

    async def search(self, product: str, brand: Optional[str], pincode: Optional[str]) -> PlatformResult:
        query    = f"{brand} {product}".strip() if brand else product
        captured = []

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(
                    headless=True,
                    args=[
                        "--no-sandbox",
                        "--disable-setuid-sandbox",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-dev-shm-usage",
                    ],
                )
                context = await browser.new_context(
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    viewport={"width": 1280, "height": 800},
                    locale="en-IN",
                    timezone_id="Asia/Kolkata",
                    extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
                )
                page = await context.new_page()

                async def intercept(response):
                    if (
                        "user-search-service/api/v3/search" in response.url
                        and "filters" not in response.url
                        and response.status == 200
                    ):
                        try:
                            captured.append(await response.json())
                        except Exception:
                            pass

                page.on("response", intercept)

                await page.goto(
                    f"https://www.zeptonow.com/search?query={query}",
                    wait_until="networkidle",
                    timeout=30000,
                )
                await page.wait_for_timeout(4000)
                await browser.close()

        except Exception as e:
            return self._error(str(e))

        if not captured:
            return self._error("No v3/search response captured")

        data     = captured[-1]
        layout   = data.get("layout", [])
        products = []

        for widget in layout:
            if widget.get("widgetId") != "PRODUCT_GRID":
                continue
            items = (
                widget.get("data", {})
                      .get("resolver", {})
                      .get("data", {})
                      .get("items", [])
            )
            for item in items:
                pr      = item.get("productResponse", {})
                prod    = pr.get("product", {})
                variant = pr.get("productVariant", {})

                name = prod.get("name", "")
                if not name:
                    continue

                # Prices are in PAISE — divide by 100
                # Avoid 'price' field — it's a dict in Zepto's API
                mrp_raw   = pr.get("mrp", 0) or 0
                sell_raw  = pr.get("discountedSellingPrice") or pr.get("sellingPrice") or mrp_raw

                mrp   = float(mrp_raw)   / 100
                price = float(sell_raw)  / 100

                if price == 0:
                    price = mrp

                # Image
                images   = variant.get("images", [])
                img_path = images[0].get("path", "") if images else ""
                img_url  = f"{IMAGE_BASE}{img_path}" if img_path else None

                # Quantity from formattedPacksize e.g. "1 pack (140 g)"
                qty_str = variant.get("formattedPacksize", "1 piece")

                # In stock
                in_stock = not bool(pr.get("outOfStock", False))

                products.append(RawProduct(
                    platform=self.PLATFORM,
                    product_id=str(pr.get("id", pr.get("objectId", ""))),
                    name=name,
                    brand=prod.get("brand") if isinstance(prod.get("brand"), str) else None,
                    image_url=img_url,
                    mrp=mrp,
                    selling_price=price,
                    discount_pct=self._discount(mrp, price),
                    quantity_str=qty_str,
                    in_stock=in_stock,
                    delivery_time_min=None,
                    product_url=f"https://www.zeptonow.com/search?query={name.replace(' ', '%20')}",
                    scraped_at=datetime.now(timezone.utc),
                ))

        return self._success(products) if products else self._error("0 products parsed")

    def _success(self, products):
        return PlatformResult(platform=self.PLATFORM, products=products)

    def _error(self, error):
        return PlatformResult(platform=self.PLATFORM, products=[], error=error)

    @staticmethod
    def _discount(mrp, price):
        if mrp <= 0 or price >= mrp:
            return 0.0
        return round((mrp - price) / mrp * 100, 1)
