# Price Comparison Agent

LangGraph-powered agentic AI that compares grocery prices in real-time across **Zepto** and **Blinkit** using Playwright browser automation.

---

## Architecture

```
START
 └─► query_parser          ← Groq Llama-3.1-8b extracts product/brand/unit/qty
      ├─[invalid]─► error_handler ──► END
      └─[valid]──► cache_check     ← Redis, 5-min TTL
            ├─[hit]──► response_router ──► END
            └─[miss]─► (parallel fan-out)
                  ├─► scraper_zepto    ─┐  Playwright intercepts
                  └─► scraper_blinkit  ─┘  XHR API responses
                           └─► normalizer    ← unit/weight disambiguation
                                └─► aggregator   ← ranking + badge assignment
                                     ├─[results]──► response_router ──► END
                                     └─[empty]───► error_handler ──► END
```

---

## Project Structure

```
price_comparison_agent/
├── src/
│   ├── agent/
│   │   ├── state.py              # AgentState TypedDict
│   │   ├── graph.py              # LangGraph graph (Zepto + Blinkit)
│   │   ├── nodes/
│   │   │   ├── query_parser.py   # Groq LLM query extraction
│   │   │   ├── cache_check.py    # Redis cache lookup
│   │   │   ├── normalizer.py     # Unit normalisation + price-per-unit
│   │   │   ├── aggregator.py     # Ranking + badge assignment
│   │   │   ├── router.py         # Response routing + analytics
│   │   │   ├── error_handler.py  # Error surfacing
│   │   │   └── scrapers/
│   │   │       ├── base.py           # Abstract scraper
│   │   │       ├── base_playwright.py # Shared browser pool
│   │   │       ├── zepto.py          # Zepto Playwright scraper
│   │   │       ├── blinkit.py        # Blinkit Playwright scraper
│   │   │       └── _runner.py        # Node functions + retry
│   │   └── edges/
│   │       └── conditions.py     # Conditional routing functions
│   ├── models/
│   │   ├── query.py              # ParsedQuery
│   │   └── product.py            # RawProduct → PriceComparison
│   ├── infrastructure/
│   │   ├── cache.py              # Redis wrapper (failure-safe)
│   │   ├── rate_limiter.py       # Token-bucket per platform
│   │   ├── http_client.py        # Async HTTP/2 + retry
│   │   └── observability.py      # Prometheus + structlog + Sentry
│   └── api/
│       ├── main.py               # FastAPI app factory + lifespan
│       └── routes.py             # REST + SSE endpoints
├── tests/
│   ├── unit/
│   │   ├── test_normalizer.py
│   │   └── test_aggregator.py
│   └── integration/
│       └── test_agent.py
├── streamlit_app.py              # Streamlit UI
├── Dockerfile
├── docker-compose.yml
├── prometheus.yml
├── pyproject.toml
├── requirements.txt
└── .env.example
```

---

GitHub repo (source)
    │
    ├─► Hugging Face Spaces (Docker)  ← FastAPI + LangGraph + Playwright
    │       └── uses Upstash Redis for caching
    │
    └─► Streamlit Community Cloud     ← UI
            └── calls Hugging Face API


## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/amanahmad1607/price-comparison-agent

python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Install Playwright Chromium (one-time, ~200MB)
playwright install chromium
playwright install-deps chromium
```

### 2. Configure environment

```bash
cp .env.example .env
nano .env
```

Minimum required:

```bash
GROQ_API_KEY=gsk_...        # free at console.groq.com
REDIS_URL=redis://localhost:6379/0
```

### 3. Start Redis

```bash
docker compose up redis -d
```

### 4. Run tests

```bash
# Install test deps
pip install pytest pytest-asyncio pytest-mock pytest-cov "fakeredis[aioredis]"

# Run all tests (no network, no Docker needed)
pytest tests/ -v
```

### 5. Start the API server

```bash
PYTHONPATH=. uvicorn src.api.main:app --reload --port 8001
```

### 6. Start the Streamlit UI (separate terminal)

```bash
streamlit run streamlit_app.py
# Opens at http://localhost:8501
```

---

## API Endpoints

| Method   | Path                | Description                          |
| -------- | ------------------- | ------------------------------------ |
| `POST` | `/compare`        | Full JSON price comparison           |
| `POST` | `/compare/stream` | SSE streaming — progressive results |
| `GET`  | `/health`         | Liveness probe                       |
| `GET`  | `/ready`          | Readiness probe (checks Redis)       |
| `GET`  | `/metrics`        | Prometheus metrics                   |
| `GET`  | `/docs`           | Swagger UI                           |

### Example request

```bash
curl -s -X POST http://localhost:8001/compare \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Maggi masala noodles 70g",
    "pincode": "560001"
  }' | python3 -m json.tool
```

### Example response

```json
{
  "session_id": "a1b2c3...",
  "cache_hit": false,
  "duration_ms": 14800,
  "comparison": {
    "query": "Maggi masala noodles 70g",
    "cheapest_platform": "zepto",
    "fastest_delivery_platform": "blinkit",
    "best_value_platform": "zepto",
    "platform_summaries": [
      {
        "platform": "zepto",
        "best_price": 13.0,
        "best_product_name": "MAGGI 2-Minute Instant Noodles Masala 70g",
        "discount_pct": 13.3,
        "price_per_unit": 0.186,
        "price_per_unit_label": "₹0.186/g",
        "badge": "Cheapest"
      },
      {
        "platform": "blinkit",
        "best_price": 20.0,
        "best_product_name": "Maggi Double Masala Instant Noodles",
        "discount_pct": 0.0,
        "price_per_unit": 0.286,
        "price_per_unit_label": "₹0.286/g",
        "badge": "Best value"
      }
    ]
  }
}
```

---

## How scrapers work

Both scrapers use **Playwright** (real Chromium browser) instead of direct HTTP calls, because Zepto and Blinkit use AWS CloudFront with bot detection that blocks raw requests.

**Zepto** — navigates to `zeptonow.com/search?query=...` and intercepts the XHR response from `bff-gateway.zepto.com/user-search-service/api/v3/search`. Prices are returned in **paise** (divide by 100 for INR). Product data is nested inside `layout[].widgetId == "PRODUCT_GRID"`.

**Blinkit** — navigates to `blinkit.com/s/?q=...` and intercepts `blinkit.com/v1/layout/search`. Prices are returned as formatted strings like `"₹74"` inside `response.snippets[].data.normal_price.text`.

---

## Running tests

```bash
# All tests — uses mocked scrapers + fakeredis (no real network)
pytest tests/ -v

# With coverage
pytest tests/ -v --cov=src --cov-report=term-missing

# Unit tests only (fastest)
pytest tests/unit/ -v

# Integration tests
pytest tests/integration/ -v
```

---

## Production deployment

```bash
# Build and start full stack
docker compose up -d

# Logs
docker compose logs -f agent

# Scale
docker compose up -d --scale agent=2
```

- API: http://localhost:8001
- Streamlit UI: http://localhost:8501
- Prometheus: http://localhost:9090
- API docs: http://localhost:8001/docs

---

## Key design decisions

**Parallel fan-out** — `route_after_cache` returns a list `["scraper_zepto", "scraper_blinkit"]` on cache miss. LangGraph dispatches both simultaneously. State uses `Annotated[list, operator.add]` so each scraper appends to `platform_results` without overwriting.

**Playwright XHR interception** — instead of parsing HTML, the scrapers register response listeners before navigating and capture the JSON API responses the browser receives. This is more reliable than CSS selectors and survives UI redesigns.

**Prices in paise** — Zepto's API returns prices multiplied by 100 (paise). Always divide by 100 before storing.

**Failure-safe cache** — `RedisCache` swallows all exceptions. A Redis outage degrades to live scraping, never a 500 error.

**Test patching strategy** — integration tests patch `_run_platform` (called at runtime), not the node functions (captured at graph-build time by `with_tracing()`). This is why mocks work correctly in the test suite.
