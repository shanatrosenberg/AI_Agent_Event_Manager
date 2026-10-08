from __future__ import annotations

from typing import Any

from models.submission import TalkSubmission, utc_now
from services.embeddings import TOKEN_PATTERN

BADGE_HIGH_INNOVATION = "High Innovation"
BADGE_MODERATE_NOVELTY = "Moderate Novelty"
BADGE_REDUNDANT = "Redundant / Low Novelty"
RECOMMENDATION_AI_APPROVED = BADGE_HIGH_INNOVATION
RECOMMENDATION_HIGH_RELEVANCE = BADGE_MODERATE_NOVELTY
RECOMMENDATION_NEEDS_REVIEW = BADGE_REDUNDANT
RECOMMENDATIONS = (
    BADGE_HIGH_INNOVATION,
    BADGE_MODERATE_NOVELTY,
    BADGE_REDUNDANT,
)


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, int(value)))


def lexical_overlap(left: str, right: str) -> float:
    left_tokens = set(TOKEN_PATTERN.findall((left or "").lower()))
    right_tokens = set(TOKEN_PATTERN.findall((right or "").lower()))
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)


def combined_overlap(semantic: float, lexical: float) -> float:
    return max(0.0, min(1.0, max(float(semantic or 0), float(lexical or 0))))


def innovation_score_from_overlap(top_overlap: float, strong_matches: int, catalog_size: int) -> int:
    if catalog_size <= 0 or top_overlap <= 0:
        return 94
    strong = max(0, int(strong_matches))
    if top_overlap >= 0.45 or (strong >= 2 and top_overlap >= 0.38):
        penalty = min(12, max(0, strong - 1) * 6)
        return _clamp(round(50 - (top_overlap - 0.45) * 80 - penalty), 0, 50)
    if top_overlap <= 0.20:
        return _clamp(round(85 + (0.20 - top_overlap) * 75), 85, 100)
    return _clamp(round(84 - ((top_overlap - 0.20) / 0.25) * 33), 51, 84)


def innovation_badge(score: int) -> str:
    if score >= 85:
        return BADGE_HIGH_INNOVATION
    if score <= 50:
        return BADGE_REDUNDANT
    return BADGE_MODERATE_NOVELTY


def recommend_status(score: int) -> str:
    return innovation_badge(score)


def score_rationale(score: int, badge: str, overlapping: list[dict[str, Any]] | None = None) -> str:
    notable = [hit for hit in (overlapping or []) if float(hit.get("overlap") or 0) >= 0.22]
    top = notable[0] if notable else None
    title = (top.get("title") or top.get("id") if top else "") or ""
    percent = round(float(top.get("overlap") or 0) * 100) if top else None
    if badge == BADGE_REDUNDANT:
        if title and percent is not None:
            return f"Low novelty: this proposal closely repeats {title} ({percent}% overlap)."
        return "Low novelty: the abstract repeats ideas already in the program."
    if badge == BADGE_HIGH_INNOVATION:
        return "High novelty: the abstract introduces a distinct angle not covered by existing talks."
    if title and percent is not None:
        return f"Moderate novelty: it shares some ground with {title} ({percent}% overlap)."
    return "Moderate novelty: the talk is partly original compared with the current program."


def _speaker_name(submission: TalkSubmission) -> str:
    speaker = getattr(submission, "speaker", None)
    return (getattr(speaker, "name", None) or submission.speaker_id or "").strip()


def _speaker_bio(submission: TalkSubmission) -> str:
    speaker = getattr(submission, "speaker", None)
    return (getattr(speaker, "bio", None) or "").strip()


def overlap_value(hit: dict[str, Any] | None) -> float:
    if not hit:
        return 0.0
    raw = hit.get("overlap")
    if raw is None:
        raw = hit.get("score") or 0
    try:
        return float(raw)
    except (TypeError, ValueError):
        return 0.0


def talk_name_key(hit: dict[str, Any] | None) -> str:
    if not hit:
        return ""
    return str(hit.get("title") or hit.get("id") or "").strip().lower()


def dedupe_overlap_talks(hits: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Keep one entry per talk name, preferring the highest overlap score."""
    best: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for hit in hits or []:
        if not isinstance(hit, dict):
            continue
        key = talk_name_key(hit)
        if not key:
            continue
        current = best.get(key)
        if current is None:
            best[key] = hit
            order.append(key)
        elif overlap_value(hit) > overlap_value(current):
            best[key] = hit
    return [best[key] for key in order]


def _proposal_text(submission: TalkSubmission) -> str:
    return " ".join(
        part
        for part in (
            submission.title or "",
            submission.abstract or "",
            submission.category or "",
        )
        if part
    )


class AIAssessmentAgent:
    """Deep Agent: innovation and uniqueness review against the existing talk catalog."""

    def evaluate(self, submission: TalkSubmission) -> dict[str, Any]:
        speaker_name = _speaker_name(submission)
        speaker_bio = _speaker_bio(submission)
        proposal_text = _proposal_text(submission)

        catalog: list[dict[str, Any]] = []
        rag_enabled = False
        try:
            from services.embeddings import proposal_document
            from services.vector_store import compare_against_program

            document = proposal_document(
                title=submission.title or "",
                abstract=submission.abstract or "",
                category=submission.category or "",
                speaker_name=speaker_name,
                speaker_bio=speaker_bio,
            )
            catalog = compare_against_program(
                document,
                exclude_source_id=submission.id,
                backfill=False,
            )
            rag_enabled = True
        except Exception:
            catalog = []

        overlapping: list[dict[str, Any]] = []
        for hit in catalog:
            lexical = lexical_overlap(
                proposal_text,
                " ".join(
                    part
                    for part in (hit.get("title") or "", hit.get("abstract") or "", hit.get("category") or "")
                    if part
                ),
            )
            overlap = combined_overlap(float(hit.get("score") or 0), lexical)
            overlapping.append(
                {
                    **hit,
                    "overlap": round(overlap, 4),
                    "lexical_overlap": round(lexical, 4),
                    "semantic_score": hit.get("score"),
                }
            )
        overlapping.sort(key=lambda item: overlap_value(item), reverse=True)
        overlapping = dedupe_overlap_talks(overlapping)

        top_overlap = float(overlapping[0]["overlap"]) if overlapping else 0.0
        strong_matches = [hit for hit in overlapping if float(hit.get("overlap") or 0) >= 0.35]
        score = innovation_score_from_overlap(top_overlap, len(strong_matches), len(overlapping))
        badge = innovation_badge(score)
        confidence_score = _clamp(
            48 + min(36, len(overlapping) * 4) + (10 if rag_enabled else 0),
            20,
            98,
        )
        summary = self._uniqueness_summary(score, badge, overlapping, rag_enabled)
        rationale = score_rationale(score, badge, overlapping)
        mcp_tools = self._invoke_mcp_tools(submission, speaker_name)
        web_check = mcp_tools.get("tavily_web_speaker_search") or {}
        venue_check = mcp_tools.get("venue_capacity_validator") or {}
        web_results = web_check.get("results") or []
        if web_check.get("verified") and web_results:
            summary = f"{summary} {web_check.get('verification_badge')}: {len(web_results)} public source(s)."
        elif web_check.get("enabled") and web_check.get("error"):
            summary = f"{summary} Tavily search could not complete."
        if venue_check.get("issues"):
            summary = f"{summary} Venue check: {venue_check['issues'][0]}"

        return {
            "status": "complete",
            "agent_status": "complete",
            "innovation_score": score,
            "innovation_badge": badge,
            "quality_score": score,
            "confidence_score": confidence_score,
            "recommendation": badge,
            "recommended_status": badge,
            "summary": summary,
            "uniqueness_summary": summary,
            "score_rationale": rationale,
            "similar_talks": overlapping[:8],
            "overlapping_talks": overlapping[:8],
            "catalog_size": len(overlapping),
            "top_overlap": round(top_overlap, 4),
            "web_check": web_check,
            "tavily_verified": bool(web_check.get("verified")),
            "tavily_badge": web_check.get("verification_badge"),
            "venue_check": venue_check,
            "mcp_tools": mcp_tools,
            "assessed_at": utc_now().isoformat(timespec="seconds"),
            "hooks": {
                "vector_rag": {
                    "enabled": rag_enabled,
                    "purpose": "Compare title and abstract against approved and pending talks for uniqueness",
                    "matches": len(overlapping),
                    "top_overlap": round(top_overlap, 4),
                },
                "mcp_tavily": {
                    "enabled": bool(web_check.get("enabled")),
                    "invoked": "tavily_web_speaker_search" in mcp_tools.get("invoked", []),
                    "purpose": "Verify speaker credentials and topic relevance via the Tavily MCP tool",
                    "matches": len(web_results),
                    "note": web_check.get("note") or web_check.get("error"),
                },
                "mcp_venue": {
                    "enabled": bool(venue_check),
                    "invoked": "venue_capacity_validator" in mcp_tools.get("invoked", []),
                    "purpose": "Validate hall capacity and scheduling conflicts via MCP",
                    "valid": venue_check.get("valid"),
                },
            },
        }

    def enqueue(self, submission: TalkSubmission) -> dict[str, Any]:
        """Run the uniqueness review immediately and mark the proposal for background catch-up."""
        assessment = self.evaluate(submission)
        assessment["queued_for_background_agent"] = True
        return assessment

    def _uniqueness_summary(
        self,
        score: int,
        badge: str,
        overlapping: list[dict[str, Any]],
        rag_enabled: bool,
    ) -> str:
        notable = [hit for hit in overlapping if float(hit.get("overlap") or 0) >= 0.22][:3]
        names = []
        for hit in notable:
            title = hit.get("title") or hit.get("id")
            percent = round(float(hit.get("overlap") or 0) * 100)
            names.append(f"{title} ({percent}% overlap)")
        if not overlapping:
            if rag_enabled:
                return (
                    f"Innovation score {score}/100. This proposal introduces a fresh angle; "
                    "no approved or pending talks overlap with its title or abstract."
                )
            return f"Innovation score {score}/100. Uniqueness review could not query the talk catalog."
        if badge == BADGE_REDUNDANT:
            repeated = ", ".join(names) if names else overlapping[0].get("title") or "an existing talk"
            return (
                f"Innovation score {score}/100. This proposal is repetitive and overlaps existing talks: {repeated}."
            )
        if badge == BADGE_HIGH_INNOVATION:
            extra = f" Closest existing talks are only weakly related: {', '.join(names)}." if names else ""
            return (
                f"Innovation score {score}/100. The abstract introduces unique content "
                f"not heavily covered by the current program.{extra}"
            )
        extra = f" It shares some ground with {', '.join(names)}." if names else ""
        return f"Innovation score {score}/100. The talk is partly original but not fully unique.{extra}"

    def _invoke_mcp_tools(self, submission: TalkSubmission, speaker_name: str) -> dict[str, Any]:
        from mcp.client import default_mcp_client
        from mcp.tools.tavily_search import TOOL_NAME as TAVILY_TOOL
        from mcp.tools.venue_validator import TOOL_NAME as VENUE_TOOL

        client = default_mcp_client()
        invoked: list[str] = []
        payload: dict[str, Any] = {"invoked": invoked}
        if self._should_search_web(submission, speaker_name) and client.has_tool(TAVILY_TOOL):
            payload[TAVILY_TOOL] = client.call_tool(
                TAVILY_TOOL,
                {
                    "speaker_name": speaker_name,
                    "title": submission.title or "",
                    "topic": submission.title or "",
                    "category": submission.category or "",
                    "max_results": 5,
                },
            )
            invoked.append(TAVILY_TOOL)
        if self._should_validate_venue(submission) and client.has_tool(VENUE_TOOL):
            payload[VENUE_TOOL] = client.call_tool(
                VENUE_TOOL,
                {
                    "capacity": submission.capacity,
                    "date": submission.date or "",
                    "start_time": submission.start_time or "",
                    "end_time": submission.end_time or "",
                    "exclude_event_id": submission.event_id or "",
                },
            )
            invoked.append(VENUE_TOOL)
        return payload

    def _should_search_web(self, submission: TalkSubmission, speaker_name: str) -> bool:
        return bool((speaker_name or "").strip() or (submission.title or "").strip())

    def _should_validate_venue(self, submission: TalkSubmission) -> bool:
        return any(
            [
                submission.capacity is not None,
                submission.date,
                submission.start_time,
                submission.end_time,
            ]
        )
