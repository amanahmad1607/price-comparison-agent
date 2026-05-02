"""
src/agent/nodes/scrapers/base_playwright.py
---------------------------------------------
Shared Playwright browser pool — reused across Zepto and Blinkit scrapers.
"""
from __future__ import annotations
import asyncio
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page

_browser: Optional[Browser] = None
_playwright = None
_lock = asyncio.Lock()

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def get_browser() -> Browser:
    global _browser, _playwright
    async with _lock:
        if _browser is None or not _browser.is_connected():
            _playwright = await async_playwright().start()
            _browser = await _playwright.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-blink-features=AutomationControlled",
                    "--disable-dev-shm-usage",
                ],
            )
    return _browser


async def new_page() -> Page:
    browser = await get_browser()
    context = await browser.new_context(
        user_agent=_UA,
        viewport={"width": 1280, "height": 800},
        locale="en-IN",
        timezone_id="Asia/Kolkata",
        extra_http_headers={"Accept-Language": "en-IN,en;q=0.9"},
    )
    page = await context.new_page()
    return page


async def close_browser() -> None:
    global _browser, _playwright
    if _browser:
        await _browser.close()
        _browser = None
    if _playwright:
        await _playwright.stop()
        _playwright = None
