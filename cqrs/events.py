"""Canonical domain events for Event Sourcing."""

from __future__ import annotations

from typing import Any

TALK_PROPOSED = "TalkProposed"
TALK_INNOVATION_REVIEWED = "TalkInnovationReviewed"
TALK_APPROVED = "TalkApproved"
TALK_REJECTED = "TalkRejected"

EVENT_ALIASES = {
    "TalkSubmitted": TALK_PROPOSED,
    "TalkAssessedByAgent": TALK_INNOVATION_REVIEWED,
}

TALK_LIFECYCLE_EVENTS = frozenset(
    {
        TALK_PROPOSED,
        TALK_INNOVATION_REVIEWED,
        TALK_APPROVED,
        TALK_REJECTED,
        "TalkQueuedForAssessment",
        "TalkPublished",
        "TalkConfirmedBySpeaker",
        "TalkConfirmationDeclined",
        "TalkRestored",
        "TalkDeleted",
        "TalkPurged",
        *EVENT_ALIASES.keys(),
    }
)

EVENT_LABELS = {
    TALK_PROPOSED: "Talk proposed",
    TALK_INNOVATION_REVIEWED: "Innovation reviewed",
    TALK_APPROVED: "Talk approved",
    TALK_REJECTED: "Talk rejected",
    "TalkQueuedForAssessment": "Queued for AI assessment",
    "TalkPublished": "Talk published",
    "TalkConfirmedBySpeaker": "Speaker confirmed",
    "TalkConfirmationDeclined": "Speaker declined",
    "TalkRestored": "Talk restored",
    "TalkDeleted": "Talk deleted",
    "TalkPurged": "Talk purged",
    "TalkRequested": "Speaker invited",
    "TalkRequestAccepted": "Invitation accepted",
    "TalkRequestDeclined": "Invitation declined",
    "EventCreated": "Event created",
    "EventUpdated": "Event updated",
    "EventDisapproved": "Event disapproved",
    "EventRestored": "Event restored",
    "EventDeleted": "Event deleted",
    "SeatReserved": "Seat reserved",
    "AttendeeRegistered": "Attendee registered",
    "AccountRegistered": "Account registered",
    "UserLoggedIn": "User signed in",
    "SpeakerNotified": "Speaker notified",
}


def canonicalize(event_name: str | None) -> str:
    name = str(event_name or "").strip()
    return EVENT_ALIASES.get(name, name)


def event_label(event_name: str | None) -> str:
    name = canonicalize(event_name)
    if name in EVENT_LABELS:
        return EVENT_LABELS[name]
    raw = str(event_name or "Domain event").strip() or "Domain event"
    spaced = "".join(f" {char}" if char.isupper() else char for char in raw).strip()
    return spaced or raw


def infer_aggregate_type(event_name: str | None, payload: dict[str, Any] | None = None) -> str:
    name = canonicalize(event_name)
    payload = payload or {}
    if payload.get("submission_id") or name in TALK_LIFECYCLE_EVENTS or name.startswith("Talk"):
        if name.startswith("TalkRequest"):
            return "talk_request"
        return "talk"
    if name.startswith("Event"):
        return "event"
    if name in {"SeatReserved", "AttendeeRegistered"}:
        return "booking"
    if name in {"AccountRegistered", "UserLoggedIn"}:
        return "account"
    if name.startswith("TalkRequest"):
        return "talk_request"
    return "domain"


def infer_aggregate_id(payload: dict[str, Any] | None, event_name: str | None = None) -> str | None:
    payload = payload or {}
    name = canonicalize(event_name)
    preferred = ("id", "submission_id", "event_id", "request_id", "user_id")
    if name in {"SeatReserved", "AttendeeRegistered"}:
        preferred = ("event_id", "id", "attendee_id")
    elif name in {"AccountRegistered", "UserLoggedIn"}:
        preferred = ("user_id", "id")
    elif name.startswith("TalkRequest"):
        preferred = ("id", "request_id", "submission_id")
    elif name.startswith("Event"):
        preferred = ("id", "event_id")
    for key in preferred:
        value = payload.get(key)
        if value:
            return str(value)
    return None


def event_summary(event_name: str | None, payload: dict[str, Any] | None = None) -> str:
    payload = payload or {}
    name = canonicalize(event_name)
    title = str(payload.get("title") or payload.get("topic") or "").strip()
    speaker = str(payload.get("speaker_name") or payload.get("speaker_id") or "").strip()
    status = str(payload.get("status") or "").replace("_", " ").strip()
    assessment = payload.get("ai_assessment") if isinstance(payload.get("ai_assessment"), dict) else {}
    score = payload.get("innovation_score")
    if score is None:
        score = assessment.get("innovation_score")
    badge = payload.get("innovation_badge") or assessment.get("innovation_badge")
    if name == TALK_INNOVATION_REVIEWED:
        parts = []
        if score is not None:
            parts.append(f"Innovation Score {score}")
        if badge:
            parts.append(str(badge))
        if title:
            parts.append(title)
        return " · ".join(parts) or event_label(name)
    if name == TALK_REJECTED:
        note = str(payload.get("rejection_message") or payload.get("message") or "").strip()
        return " · ".join(item for item in (title, note) if item) or event_label(name)
    if name == TALK_APPROVED:
        return " · ".join(item for item in (title, "Added to the official program") if item)
    parts = [item for item in (title, speaker, status) if item]
    return " · ".join(parts) or event_label(name)
