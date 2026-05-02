"""
tests.integration
-----------------
Integration tests — run the full LangGraph graph end-to-end.

All external I/O is replaced with deterministic fakes:
  - LLM         → AsyncMock returning fixed JSON
  - Scrapers    → async functions returning hardcoded PlatformResult objects
  - Redis       → fakeredis.aioredis.FakeRedis (in-memory, no Docker needed)
  - Rate limiter → RateLimiter with 1000 req/s limit (effectively unlimited)

Scenarios covered:
  test_happy_path_all_platforms         — 2 scrapers succeed, correct cheapest picked
  test_invalid_query_routed_to_error    — short query → error_handler → no comparison
  test_cache_hit_skips_scrapers         — cache hit → scrapers never called
  test_partial_scraper_failure          — 1 fail, 1 succeed → comparison with platforms
  test_all_scrapers_fail_routes_to_error — all fail → error_message, no comparison
"""