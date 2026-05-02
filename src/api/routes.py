"""
src/api/routes.py
------------------
FastAPI route handlers — REST + SSE endpoints for Zepto + Blinkit agent.
"""
from __future__ import annotations
import time, uuid, json, logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from src.agent.state import initial_state, AgentState
from src.models.product import PriceComparison

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_PLATFORMS = ["zepto", "blinkit"]


class CompareRequest(BaseModel):
    query: str = Field(..., min_length=3, max_length=200,
                       examples=["Maggi 70g", "Amul toned milk 500ml"])
    pincode: Optional[str] = Field(None, pattern=r"^\d{6}$", examples=["560001"])
    platforms: list[str] = Field(default_factory=list,
                                 examples=[["zepto", "blinkit"]])
    user_id: Optional[str] = None


class CompareResponse(BaseModel):
    session_id: str
    comparison: Optional[PriceComparison] = None
    error: Optional[str] = None
    cache_hit: bool = False
    duration_ms: float
    platforms_searched: list[str] = Field(default_factory=list)
    platforms_failed: list[str] = Field(default_factory=list)


def _failed(state: AgentState) -> list[str]:
    return [s["platform"] for s in state.get("scraper_statuses", [])
            if s["status"] != "success"]


@router.post("/compare", response_model=CompareResponse)
async def compare_prices(req: CompareRequest, request: Request):
    """Compare prices across Zepto and Blinkit."""
    agent      = request.app.state.agent
    session_id = str(uuid.uuid4())

    # Filter to only valid platforms
    plat_filter = [p for p in req.platforms if p in VALID_PLATFORMS]

    state = initial_state(
        raw_query=req.query.strip(),
        session_id=session_id,
        user_id=req.user_id,
        pincode=req.pincode,
        platform_filter=plat_filter,
        channel="api",
    )

    t0 = time.perf_counter()
    try:
        result: AgentState = await agent.ainvoke(
            state, config={"configurable": {"thread_id": session_id}},
        )
    except Exception as exc:
        logger.exception("Agent failed session=%s", session_id)
        raise HTTPException(status_code=500, detail=str(exc))

    duration   = round((time.perf_counter() - t0) * 1000, 1)
    comparison = result.get("price_comparison") or result.get("cached_result")

    return CompareResponse(
        session_id=session_id,
        comparison=comparison,
        error=result.get("error_message"),
        cache_hit=result.get("cache_hit", False),
        duration_ms=duration,
        platforms_searched=result.get("parsed_query").platforms if result.get("parsed_query") else [],
        platforms_failed=_failed(result),
    )


@router.post("/compare/stream")
async def compare_stream(req: CompareRequest, request: Request):
    """SSE streaming endpoint — emits events as each scraper finishes."""
    agent      = request.app.state.agent
    session_id = str(uuid.uuid4())
    plat_filter = [p for p in req.platforms if p in VALID_PLATFORMS]

    state = initial_state(
        raw_query=req.query.strip(),
        session_id=session_id,
        pincode=req.pincode,
        platform_filter=plat_filter,
        channel="web",
    )

    async def event_stream():
        try:
            async for event in agent.astream_events(
                state,
                config={"configurable": {"thread_id": session_id}},
                version="v2",
            ):
                kind = event.get("event", "")
                name = event.get("name", "")
                if kind == "on_chain_start":
                    yield f"data: {json.dumps({'type':'node_start','node':name})}\n\n"
                elif kind == "on_chain_end":
                    output = event.get("data", {}).get("output", {})
                    for pr in output.get("platform_results", []):
                        yield f"data: {json.dumps({'type':'platform_result','platform':pr['platform'],'count':len(pr.get('products',[]))})}\n\n"
                    if output.get("price_comparison"):
                        pc = output["price_comparison"]
                        yield f"data: {json.dumps({'type':'comparison_ready','data': pc.model_dump(mode='json') if hasattr(pc,'model_dump') else pc})}\n\n"
                    yield f"data: {json.dumps({'type':'node_end','node':name})}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type':'error','message':str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_stream(), media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/health")
async def health():
    return {"status": "ok", "platforms": ["zepto", "blinkit"]}


@router.get("/ready")
async def ready(request: Request):
    from src.agent.nodes.cache_check import _cache
    redis_ok = await _cache.ping() if _cache else False
    if not redis_ok:
        raise HTTPException(status_code=503, detail="Redis not reachable")
    return {"status": "ready", "redis": "ok"}
