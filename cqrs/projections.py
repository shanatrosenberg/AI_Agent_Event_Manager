"""Rebuild read-model snapshots by folding the immutable event stream."""

from __future__ import annotations

from typing import Any, Iterable

from cqrs.events import (
    TALK_APPROVED,
    TALK_INNOVATION_REVIEWED,
    TALK_LIFECYCLE_EVENTS,
    TALK_PROPOSED,
    TALK_REJECTED,
    canonicalize,
    infer_aggregate_id,
)


def _event_name(event: Any) -> str:
    if isinstance(event, dict):
        return canonicalize(event.get("event_name") or event.get("canonical_name"))
    return canonicalize(getattr(event, "event_name", None))


def _event_payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        payload = event.get("payload")
        if isinstance(payload, dict):
            return payload
        return event
    payload = getattr(event, "payload", None)
    return payload if isinstance(payload, dict) else {}


def _event_aggregate_id(event: Any, payload: dict[str, Any], name: str) -> str | None:
    if isinstance(event, dict):
        value = event.get("aggregate_id")
        if value:
            return str(value)
    value = getattr(event, "aggregate_id", None)
    if value:
        return str(value)
    return infer_aggregate_id(payload, name)


def _merge_talk(talk: dict[str, Any], payload: dict[str, Any]) -> None:
    for key in (
        "title",
        "abstract",
        "category",
        "speaker_id",
        "speaker_name",
        "organizer_id",
        "date",
        "start_time",
        "end_time",
        "capacity",
        "event_id",
        "rejection_message",
    ):
        if payload.get(key) not in (None, ""):
            talk[key] = payload[key]
    if isinstance(payload.get("ai_assessment"), dict):
        talk["ai_assessment"] = payload["ai_assessment"]
    if payload.get("innovation_score") is not None:
        talk["innovation_score"] = payload["innovation_score"]
    elif isinstance(payload.get("ai_assessment"), dict):
        score = payload["ai_assessment"].get("innovation_score")
        if score is not None:
            talk["innovation_score"] = score
    if payload.get("innovation_badge"):
        talk["innovation_badge"] = payload["innovation_badge"]
    elif isinstance(payload.get("ai_assessment"), dict) and payload["ai_assessment"].get("innovation_badge"):
        talk["innovation_badge"] = payload["ai_assessment"]["innovation_badge"]


def _blank_talk(talk_id: str) -> dict[str, Any]:
    return {
        "id": talk_id,
        "title": None,
        "status": None,
        "speaker_id": None,
        "speaker_name": None,
        "organizer_id": None,
        "event_id": None,
        "innovation_score": None,
        "innovation_badge": None,
        "ai_assessment": {},
        "version": 0,
        "last_event": None,
    }


def project_talk_state(events: Iterable[Any]) -> dict[str, dict[str, Any]]:
    """Fold talk lifecycle events into the current state of each talk."""
    talks: dict[str, dict[str, Any]] = {}
    for event in events:
        name = _event_name(event)
        if name not in TALK_LIFECYCLE_EVENTS and name not in {
            TALK_PROPOSED,
            TALK_INNOVATION_REVIEWED,
            TALK_APPROVED,
            TALK_REJECTED,
        }:
            continue
        payload = _event_payload(event)
        talk_id = _event_aggregate_id(event, payload, name)
        if not talk_id:
            continue
        talk = talks.setdefault(talk_id, _blank_talk(talk_id))
        _merge_talk(talk, payload)
        if name == TALK_PROPOSED:
            talk["status"] = payload.get("status") or "pending_assessment"
        elif name == "TalkQueuedForAssessment":
            talk["status"] = payload.get("status") or "pending_assessment"
        elif name == TALK_INNOVATION_REVIEWED:
            talk["status"] = payload.get("status") or "under_review"
        elif name in {TALK_APPROVED, "TalkPublished", "TalkConfirmedBySpeaker"}:
            talk["status"] = "approved"
            talk["event_id"] = payload.get("event_id") or talk.get("event_id")
        elif name == TALK_REJECTED:
            talk["status"] = "rejected"
        elif name == "TalkConfirmationDeclined":
            talk["status"] = payload.get("status") or "confirmation_declined"
        elif name == "TalkRestored":
            talk["status"] = payload.get("status") or ("approved" if talk.get("event_id") else "under_review")
        elif name in {"TalkDeleted", "TalkPurged"}:
            talk["status"] = "deleted"
        talk["version"] = int(talk.get("version") or 0) + 1
        talk["last_event"] = name
    return talks


def project_talk(events: Iterable[Any], talk_id: str) -> dict[str, Any] | None:
    return project_talk_state(events).get(str(talk_id))
