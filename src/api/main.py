"""
src/api/main.py
----------------
FastAPI application factory — Zepto + Blinkit price comparison agent.

Run:
    PYTHONPATH=. uvicorn src.api.main:app --reload --port 8001
"""
from __future__ import annotations
import logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import make_asgi_app
from dotenv import load_dotenv

load_dotenv()

from src.api.routes import router
from src.agent.graph import create_agent

logger = logging.getLogger(__name__)


def _init_sentry() -> None:
    dsn = os.environ.get("SENTRY_DSN")
    if not dsn:
        return
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        sentry_sdk.init(dsn=dsn, integrations=[FastApiIntegration()],
                        traces_sample_rate=0.1,
                        environment=os.environ.get("ENVIRONMENT", "development"))
        logger.info("Sentry initialised")
    except ImportError:
        pass


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Price Comparison Agent (Zepto + Blinkit)...")
    _init_sentry()
    app.state.agent = create_agent()
    logger.info("Agent ready")
    yield
    logger.info("Shutting down...")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Price Comparison Agent",
        description="LangGraph agent comparing prices across Zepto and Blinkit.",
        version="2.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    app.include_router(router)
    app.mount("/metrics", make_asgi_app())
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8001)),
        workers=int(os.environ.get("WORKERS", 1)),
        loop="uvloop",
        reload=os.environ.get("ENVIRONMENT", "development") == "development",
    )
