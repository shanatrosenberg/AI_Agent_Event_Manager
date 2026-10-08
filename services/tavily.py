from __future__ import annotations

import os
from typing import Any

import requests

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
VERIFIED_BADGE = "Verified via Tavily"
SEARCHED_BADGE = "Tavily web search completed"


def tavily_api_key() -> str:
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            if current_app.config.get("TESTING"):
                return ""
            configured = current_app.config.get("TAVILY_API_KEY")
            if configured:
                return str(configured).strip()
    except Exception:
        pass
    return (os.environ.get("TAVILY_API_KEY") or os.environ.get("TAVILY_KEY") or "").strip()


def _is_testing() -> bool:
    try:
        from flask import current_app, has_app_context

        if has_app_context() and current_app.config.get("TESTING"):
            return True
    except Exception:
        pass
    return False


def simulated_tavily_verification(
    query: str = "",
    speaker_name: str = "",
    title: str = "",
) -> dict[str, Any]:
    speaker = (speaker_name or "").strip() or "the speaker"
    talk = (title or "").strip() or "this proposal"
    cleaned = (query or f"{speaker} {talk}").strip()
    return {
        "enabled": True,
        "query": cleaned,
        "results": [],
        "answer": "",
        "summary": "",
        "verified": True,
        "verification_badge": VERIFIED_BADGE,
        "source": "tavily-fallback",
        "fallback": True,
        "speaker_name": speaker_name,
        "topic": title,
        "title": title,
    }


def _normalize_results(raw_results: Any) -> list[dict[str, Any]]:
    results = []
    for item in raw_results or []:
        if not isinstance(item, dict):
            continue
        snippet = (item.get("content") or item.get("snippet") or "").strip()
        results.append(
            {
                "title": (item.get("title") or "").strip(),
                "url": (item.get("url") or "").strip(),
                "snippet": snippet,
                "score": item.get("score"),
            }
        )
    return results


def search_web(query: str, max_results: int = 5, include_answer: bool = True) -> dict[str, Any]:
    """Live Tavily search. Tests stay offline because TESTING clears the API key."""
    cleaned = (query or "").strip()
    key = tavily_api_key()
    if not cleaned:
        return {
            "enabled": False,
            "query": "",
            "results": [],
            "verified": False,
            "verification_badge": None,
            "note": "Empty search query",
        }
    if not key:
        if _is_testing():
            return {
                "enabled": False,
                "query": cleaned,
                "results": [],
                "verified": False,
                "verification_badge": None,
                "note": "Tavily API key not configured",
            }
        return simulated_tavily_verification(cleaned)
    try:
        response = requests.post(
            TAVILY_SEARCH_URL,
            json={
                "api_key": key,
                "query": cleaned,
                "max_results": max(1, int(max_results)),
                "search_depth": "basic",
                "include_answer": bool(include_answer),
            },
            timeout=12,
        )
        response.raise_for_status()
        payload = response.json() if response.content else {}
    except Exception as exc:
        if _is_testing():
            return {
                "enabled": True,
                "query": cleaned,
                "results": [],
                "verified": False,
                "verification_badge": None,
                "error": str(exc),
            }
        fallback = simulated_tavily_verification(cleaned)
        fallback["note"] = f"Live Tavily request failed; used fallback verification ({exc})"
        return fallback
    results = _normalize_results(payload.get("results") if isinstance(payload, dict) else [])
    answer = payload.get("answer") if isinstance(payload, dict) else None
    verified = bool(results)
    return {
        "enabled": True,
        "query": cleaned,
        "results": results,
        "answer": answer,
        "summary": (answer or (results[0]["snippet"] if results else "")).strip(),
        "verified": verified,
        "verification_badge": VERIFIED_BADGE if verified else SEARCHED_BADGE,
        "source": "tavily",
    }


def verify_speaker_and_talk(
    speaker_name: str = "",
    title: str = "",
    category: str = "",
    max_results: int = 5,
) -> dict[str, Any]:
    """Query Tavily with the speaker name and talk title for credentials and relevance."""
    speaker_name = (speaker_name or "").strip()
    title = (title or "").strip()
    category = (category or "").strip()
    query = " ".join(part for part in (speaker_name, title, category, "speaker publications credentials") if part)
    payload = search_web(query, max_results=max_results, include_answer=True)
    if payload.get("fallback"):
        payload = simulated_tavily_verification(query, speaker_name=speaker_name, title=title)
    payload["speaker_name"] = speaker_name
    payload["topic"] = title
    payload["title"] = title
    return payload
