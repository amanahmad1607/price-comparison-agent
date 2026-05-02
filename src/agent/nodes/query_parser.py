"""
src/agent/nodes/query_parser.py
---------------------------------
NODE: query_parser — LLM extracts structured query from raw user input.
Supports Zepto and Blinkit platforms.
"""
from __future__ import annotations
import json, time, logging
from langchain_core.messages import HumanMessage
from src.agent.state import AgentState
from src.models.query import ParsedQuery, ALL_PLATFORMS

logger = logging.getLogger(__name__)
_llm = None


def set_llm(llm) -> None:
    global _llm
    _llm = llm


SYSTEM_PROMPT = """You are a grocery product query parser for Indian quick-commerce apps.
Extract structured information from the user query.

Respond ONLY with a valid JSON object — no markdown, no explanation:
{
  "product_name": "<core product, e.g. toned milk>",
  "brand": "<brand name or null>",
  "quantity": <numeric amount or null>,
  "unit": "<ml|L|g|kg|pack|piece or null>",
  "category": "<dairy|snacks|beverages|... or null>",
  "max_price": <max budget in INR or null>,
  "platforms": ["zepto"|"blinkit"]
}

Rules:
- platforms: only include if user explicitly mentions zepto or blinkit; else return []
- quantity: extract the number only (e.g. "500ml" → 500, unit → "ml")
- brand: capitalise properly (e.g. "amul" → "Amul")
- product_name: lowercase, no brand, no quantity"""


async def query_parser_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    raw = state["raw_query"].strip()

    if len(raw) < 3:
        return {
            "is_valid_query": False,
            "validation_errors": ["Query is too short. Please describe what you're looking for."],
            "node_timings": {"query_parser": 0.0},
        }

    try:
        response = await _llm.ainvoke([
            HumanMessage(content=f"{SYSTEM_PROMPT}\n\nUser query: {raw}")
        ])
        raw_json = response.content.strip()
        if raw_json.startswith("```"):
            raw_json = raw_json.split("```")[1]
            if raw_json.startswith("json"):
                raw_json = raw_json[4:]

        data = json.loads(raw_json)
        parsed = ParsedQuery(**data, raw=raw)

        if state["platform_filter"]:
            parsed.platforms = [p for p in state["platform_filter"] if p in ALL_PLATFORMS]
        if not parsed.platforms:
            parsed.platforms = list(ALL_PLATFORMS)

    except json.JSONDecodeError:
        return {
            "is_valid_query": False,
            "validation_errors": ["Could not parse your query. Try being more specific."],
            "node_timings": {"query_parser": (time.perf_counter() - t0) * 1000},
        }
    except Exception as e:
        logger.exception("query_parser error")
        return {
            "is_valid_query": False,
            "validation_errors": [str(e)],
            "node_timings": {"query_parser": (time.perf_counter() - t0) * 1000},
        }

    return {
        "parsed_query": parsed,
        "is_valid_query": True,
        "validation_errors": [],
        "node_timings": {"query_parser": (time.perf_counter() - t0) * 1000},
    }
