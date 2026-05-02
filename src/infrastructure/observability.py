"""
src/infrastructure/observability.py
-------------------------------------
Prometheus metrics + structlog + with_tracing() node decorator.
"""
from __future__ import annotations
import functools, time, logging
from typing import Callable
import structlog
from prometheus_client import Counter, Histogram, Gauge

NODE_DURATION = Histogram(
    "pca_node_duration_seconds", "Execution time per agent node",
    ["node_name"], buckets=[0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
)
NODE_ERRORS    = Counter("pca_node_errors_total", "Errors per node", ["node_name"])
CACHE_OPS      = Counter("pca_cache_ops_total", "Cache ops", ["operation"])
ACTIVE_RUNS    = Gauge("pca_active_runs", "In-flight agent runs")
SCRAPER_PRODS  = Counter("pca_scraper_products_total", "Products per scraper",
                          ["platform", "status"])

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)
log = structlog.get_logger()


def with_tracing(fn: Callable) -> Callable:
    """Wrap a node with Prometheus timing, active-run gauge, and structlog."""
    node_name = fn.__name__.replace("_node", "")

    @functools.wraps(fn)
    async def wrapper(state, *args, **kwargs):
        ACTIVE_RUNS.inc()
        start = time.perf_counter()
        log.info("node.start", node=node_name, session=state.get("session_id"))
        try:
            result = await fn(state, *args, **kwargs)
            elapsed = time.perf_counter() - start
            NODE_DURATION.labels(node_name=node_name).observe(elapsed)
            log.info("node.end", node=node_name, session=state.get("session_id"),
                     duration_ms=round(elapsed * 1000, 1))
            return result
        except Exception as exc:
            NODE_ERRORS.labels(node_name=node_name).inc()
            log.error("node.error", node=node_name, session=state.get("session_id"),
                      error=str(exc), duration_ms=round((time.perf_counter()-start)*1000, 1))
            try:
                import sentry_sdk
                sentry_sdk.capture_exception(exc)
            except ImportError:
                pass
            raise
        finally:
            ACTIVE_RUNS.dec()

    return wrapper
