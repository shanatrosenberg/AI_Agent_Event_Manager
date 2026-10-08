from __future__ import annotations

from typing import Any

from mcp.protocol import ToolSpec
from services.tavily import search_web, verify_speaker_and_talk

TOOL_NAME = "tavily_web_speaker_search"


def run_tavily_web_speaker_search(arguments: dict[str, Any]) -> dict[str, Any]:
    speaker_name = str(arguments.get("speaker_name") or "").strip()
    topic = str(arguments.get("topic") or arguments.get("title") or "").strip()
    category = str(arguments.get("category") or "").strip()
    explicit = str(arguments.get("query") or "").strip()
    max_results = arguments.get("max_results", 5)
    try:
        max_results = max(1, int(max_results))
    except (TypeError, ValueError):
        max_results = 5

    if explicit:
        payload = search_web(explicit, max_results=max_results, include_answer=True)
        payload["speaker_name"] = speaker_name
        payload["topic"] = topic
        payload["title"] = topic
    else:
        payload = verify_speaker_and_talk(
            speaker_name=speaker_name,
            title=topic,
            category=category,
            max_results=max_results,
        )
    payload["tool"] = TOOL_NAME
    return payload


def tavily_web_speaker_search_tool() -> ToolSpec:
    return ToolSpec(
        name=TOOL_NAME,
        description=(
            "Search the public web with Tavily to verify speaker backgrounds, "
            "publication records, and real-time topic relevance."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Optional full search query"},
                "speaker_name": {"type": "string"},
                "topic": {"type": "string"},
                "title": {"type": "string"},
                "category": {"type": "string"},
                "max_results": {"type": "integer", "default": 3},
            },
        },
        handler=run_tavily_web_speaker_search,
    )
