"""Ollama-backed talk idea generator for the speaker Innovation Hub."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from flask import current_app

from services.ollama import DEFAULT_MODEL, OllamaError, extract_generated_text, generate, ollama_model

TRENDING_TOPICS: tuple[tuple[str, str], ...] = (
    ("AI Agents", "ai"),
    ("Cloud Security", "architecture"),
    ("RAG", "ai"),
    ("Edge AI", "ai"),
    ("Platform Engineering", "architecture"),
    ("Observability", "architecture"),
)

CURATED_IDEAS: tuple[dict[str, str], ...] = (
    {
        "title": "Agentic Workflows That Know When to Ask a Human",
        "topic": "AI Agents",
        "category": "ai",
        "abstract": "A practical session on building AI agents that plan, call tools, and escalate safely. We walk through guardrails, memory, and a conference-ops demo where an agent drafts a talk review but never publishes without a human.",
    },
    {
        "title": "Zero-Trust Talks: Cloud Security for Event Platforms",
        "topic": "Cloud Security",
        "category": "architecture",
        "abstract": "How to harden a public conference stack: identity isolation, least-privilege APIs, and secret handling when organizers, speakers, and attendees share one cloud. Includes a threat model for proposal and booking flows.",
    },
    {
        "title": "Retrieval That Does Not Repeat Last Year's Keynote",
        "topic": "RAG",
        "category": "ai",
        "abstract": "A hands-on RAG design for program uniqueness. We embed titles and abstracts, rank overlap, and show how retrieval-augmented review can flag redundant talks before they hit the schedule.",
    },
    {
        "title": "Intelligence at the Seat: Edge AI for Live Sessions",
        "topic": "Edge AI",
        "category": "ai",
        "abstract": "Moving inference out of the data center and onto venue devices. Coverage of on-device summarization, bandwidth limits, and privacy-preserving captions for hybrid conference halls.",
    },
    {
        "title": "Platform Engineering for Conference Command Centers",
        "topic": "Platform Engineering",
        "category": "architecture",
        "abstract": "Treat the event platform as an internal developer platform: golden paths for proposals, self-service halls, and paved roads from abstract to approved session without ticket ping-pong.",
    },
    {
        "title": "Seeing the Program: Observability for CQRS Event Stores",
        "topic": "Observability",
        "category": "architecture",
        "abstract": "Traces, metrics, and audit logs across an event-sourced talk lifecycle. Learn how to follow TalkProposed through innovation review to approval without losing the why behind each decision.",
    },
)


@dataclass
class IdeaHubResult:
    ideas: list[dict[str, Any]] = field(default_factory=list)
    model: str = DEFAULT_MODEL
    source: str = "ollama"
    fallback: bool = False
    message: str = ""
    error: str = ""
    status_code: int = 200


def _idea_payload(raw: dict[str, str], *, source: str) -> dict[str, Any]:
    title = " ".join((raw.get("title") or "").split()).strip()
    topic = " ".join((raw.get("topic") or "").split()).strip()
    category = (raw.get("category") or "ai").strip().lower() or "ai"
    abstract = " ".join((raw.get("abstract") or "").split()).strip()
    return {
        "id": f"idea-{uuid4().hex[:10]}",
        "title": title[:255],
        "topic": topic,
        "category": category,
        "abstract": abstract[:4000],
        "source": source,
    }


TOPIC_CATEGORY_HINTS: tuple[tuple[str, str], ...] = (
    ("agent", "ai"),
    ("rag", "ai"),
    ("llm", "ai"),
    ("language model", "ai"),
    ("machine learning", "ai"),
    ("security", "architecture"),
    ("cloud", "architecture"),
    ("microservice", "architecture"),
    ("observab", "architecture"),
    ("platform", "architecture"),
    ("devops", "architecture"),
    ("community", "community"),
    ("product", "product"),
)

IDEA_ANGLES: tuple[str, ...] = (
    "a production case study",
    "an architecture deep dive",
    "a hands-on workshop",
    "a security and ethics lens",
    "a live demo session",
    "a future-looking keynote",
)


def normalize_topic_query(value: str | None) -> str:
    return " ".join(str(value or "").split()).strip()[:128]


def category_for_topic(topic: str) -> str:
    key = (topic or "").lower()
    for hint, category in TOPIC_CATEGORY_HINTS:
        if hint in key:
            return category
    return "ai"


def curated_ideas(limit: int = 6, query: str | None = None) -> list[dict[str, Any]]:
    count = max(1, min(int(limit or 6), 6))
    topic = normalize_topic_query(query)
    if not topic:
        return [_idea_payload(dict(item), source="curated") for item in CURATED_IDEAS[:count]]
    matches = [
        item
        for item in CURATED_IDEAS
        if topic.lower() in item["topic"].lower()
        or topic.lower() in item["title"].lower()
        or topic.lower() in item["abstract"].lower()
    ]
    ideas = [_idea_payload(dict(item), source="curated") for item in matches]
    category = category_for_topic(topic)
    for angle in IDEA_ANGLES:
        if len(ideas) >= count:
            break
        ideas.append(
            _idea_payload(
                {
                    "title": f"{topic}: {angle.removeprefix('a ').removeprefix('an ').title()}",
                    "topic": topic,
                    "category": category,
                    "abstract": (
                        f"An innovative conference talk on {topic}, framed as {angle}. "
                        "Attendees leave with patterns they can apply to real event platforms, "
                        "agent workflows, and production systems."
                    ),
                },
                source="curated",
            )
        )
    return ideas[:count]


def _parse_generated_idea(text: str, topic: str, category: str) -> dict[str, str] | None:
    cleaned = extract_generated_text(text).strip()
    if not cleaned:
        return None
    if cleaned[:1] in "[{":
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, list) and parsed:
            parsed = parsed[0]
        if isinstance(parsed, dict):
            title = str(parsed.get("title") or "").strip()
            abstract = str(parsed.get("abstract") or parsed.get("summary") or "").strip()
            if title and abstract:
                return {
                    "title": title,
                    "topic": str(parsed.get("topic") or topic),
                    "category": str(parsed.get("category") or category),
                    "abstract": abstract,
                }
    title_match = re.search(r"(?im)^\s*(?:title|talk)\s*[:\-]\s*(.+)$", cleaned)
    abstract_match = re.search(r"(?im)^\s*(?:abstract|summary)\s*[:\-]\s*(.+)$", cleaned)
    if title_match and abstract_match:
        abstract = abstract_match.group(1).strip()
        rest = cleaned[abstract_match.end() :].strip()
        if rest:
            abstract = f"{abstract} {rest}".strip()
        return {
            "title": title_match.group(1).strip(),
            "topic": topic,
            "category": category,
            "abstract": abstract,
        }
    lines = [line.strip(" -•\t") for line in cleaned.splitlines() if line.strip()]
    if len(lines) >= 2:
        return {
            "title": lines[0][:255],
            "topic": topic,
            "category": category,
            "abstract": " ".join(lines[1:]),
        }
    if len(cleaned) > 40:
        sentence = cleaned.split(".")[0].strip()
        return {
            "title": (sentence[:90] or topic).rstrip("."),
            "topic": topic,
            "category": category,
            "abstract": cleaned,
        }
    return None


def _generate_one(
    topic: str,
    category: str,
    *,
    angle: str = "",
) -> dict[str, Any] | None:
    focus = f"{topic}, framed as {angle}" if angle else topic
    prompt = (
        f"Invent one original, cutting-edge conference talk about {focus}. "
        "Reply in this exact format:\n"
        "TITLE: a specific talk title\n"
        "ABSTRACT: a 2-3 sentence professional abstract"
    )
    generated = generate(prompt, max_tokens=220)
    parsed = _parse_generated_idea(generated, topic, category)
    if parsed is None:
        return None
    parsed["topic"] = topic
    parsed["category"] = category
    return _idea_payload(parsed, source="ollama")


def _topic_plan(query: str | None, count: int) -> list[tuple[str, str, str]]:
    topic = normalize_topic_query(query)
    if topic:
        category = category_for_topic(topic)
        return [(topic, category, angle) for angle in IDEA_ANGLES[:count]]
    return [(name, category, "") for name, category in TRENDING_TOPICS[:count]]


def generate_talk_ideas(limit: int = 6, query: str | None = None) -> IdeaHubResult:
    """Create a board of innovative talk concepts via local Ollama, with curated fallback."""
    count = max(1, min(int(limit or 6), 6))
    topic = normalize_topic_query(query)
    plan = _topic_plan(topic, count)
    fallback = curated_ideas(count, query=topic or None)

    generated: list[dict[str, Any]] = []
    try:
        for name, category, angle in plan:
            idea = _generate_one(name, category, angle=angle)
            if idea and idea["title"] and idea["abstract"]:
                generated.append(idea)
    except (OllamaError, OSError) as exc:
        if current_app:
            current_app.logger.warning("Idea hub Ollama call failed: %s", exc)
        return IdeaHubResult(
            ideas=fallback,
            model="local-fallback",
            source="curated",
            fallback=True,
            message="Ollama could not be reached, so curated innovation ideas are shown.",
        )
    except Exception as exc:
        if current_app:
            current_app.logger.exception("Idea hub generation failed: %s", exc)
        return IdeaHubResult(
            ideas=fallback,
            model="local-fallback",
            source="curated",
            fallback=True,
            message="Idea generation failed, so curated innovation ideas are shown.",
        )

    minimum = 2 if topic else 3
    if len(generated) < minimum:
        return IdeaHubResult(
            ideas=fallback,
            model="local-fallback",
            source="curated",
            fallback=True,
            message="Ollama returned incomplete ideas, so curated concepts are shown.",
        )
    return IdeaHubResult(ideas=generated, model=ollama_model(), source="ollama")
