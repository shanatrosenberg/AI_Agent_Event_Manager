from __future__ import annotations

import hashlib
from typing import Any

from extensions import db
from models.embedding import TalkEmbedding, utc_now
from services.embeddings import (
    cosine_similarity,
    embed_text,
    proposal_document,
    speaker_document,
)


def document_id(source_type: str, source_id: str) -> str:
    return f"{source_type}:{source_id}"


def _hash_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _upsert(
    source_type: str,
    source_id: str,
    document_text: str,
    extra: dict[str, Any] | None = None,
) -> TalkEmbedding:
    key = document_id(source_type, source_id)
    digest = _hash_text(document_text)
    row = db.session.get(TalkEmbedding, key)
    if row is None:
        row = TalkEmbedding(
            id=key,
            source_type=source_type,
            source_id=source_id,
            content_hash=digest,
            document_text=document_text,
            embedding=embed_text(document_text),
            extra=extra or {},
            updated_at=utc_now(),
        )
        db.session.add(row)
    elif row.content_hash != digest:
        row.content_hash = digest
        row.document_text = document_text
        row.embedding = embed_text(document_text)
        row.extra = extra or {}
        row.updated_at = utc_now()
    else:
        row.extra = extra or row.extra or {}
        row.updated_at = utc_now()
    db.session.commit()
    return row


def index_talk_proposal(submission) -> TalkEmbedding | None:
    if submission is None or not getattr(submission, "id", None):
        return None
    speaker = getattr(submission, "speaker", None)
    speaker_name = getattr(speaker, "name", None) or getattr(submission, "speaker_id", "")
    speaker_bio = getattr(speaker, "bio", None) or ""
    document = proposal_document(
        title=getattr(submission, "title", "") or "",
        abstract=getattr(submission, "abstract", "") or "",
        category=getattr(submission, "category", "") or "",
        speaker_name=speaker_name or "",
        speaker_bio=speaker_bio or "",
    )
    extra = {
        "title": getattr(submission, "title", ""),
        "abstract": getattr(submission, "abstract", ""),
        "category": getattr(submission, "category", ""),
        "speaker_id": getattr(submission, "speaker_id", ""),
        "speaker_name": speaker_name,
        "status": getattr(submission, "status", ""),
        "event_id": getattr(submission, "event_id", None),
    }
    row = _upsert("proposal", submission.id, document, extra)
    index_speaker_profile(getattr(submission, "speaker_id", ""), speaker_name, speaker_bio)
    return row


def index_official_event(event) -> TalkEmbedding | None:
    if event is None or not getattr(event, "id", None):
        return None
    from models.submission import TalkSubmission

    speaker = getattr(event, "speaker", None)
    speaker_name = getattr(speaker, "name", None) or getattr(event, "speaker_id", "") or ""
    speaker_bio = getattr(speaker, "bio", None) or ""
    submission = TalkSubmission.query.filter_by(event_id=event.id).first()
    category = (getattr(submission, "category", None) or "").strip() or "Session"
    document = proposal_document(
        title=getattr(event, "title", "") or "",
        abstract=getattr(event, "description", "") or "",
        category=category,
        speaker_name=speaker_name,
        speaker_bio=speaker_bio,
    )
    extra = {
        "title": getattr(event, "title", ""),
        "abstract": getattr(event, "description", ""),
        "category": category,
        "speaker_id": getattr(event, "speaker_id", ""),
        "speaker_name": speaker_name,
        "status": getattr(event, "status", ""),
        "event_id": event.id,
    }
    return _upsert("event", event.id, document, extra)


def index_speaker_profile(speaker_id: str, speaker_name: str = "", speaker_bio: str = "") -> TalkEmbedding | None:
    speaker_id = (speaker_id or "").strip()
    if not speaker_id:
        return None
    from models.submission import TalkSubmission

    talks = TalkSubmission.query.filter_by(speaker_id=speaker_id).all()
    documents = [f"{item.title}. {item.abstract}" for item in talks]
    document = speaker_document(name=speaker_name or speaker_id, bio=speaker_bio, talks=documents)
    extra = {
        "speaker_id": speaker_id,
        "speaker_name": speaker_name or speaker_id,
        "talk_count": len(talks),
    }
    return _upsert("speaker", speaker_id, document, extra)


def remove_document(source_type: str, source_id: str) -> None:
    row = db.session.get(TalkEmbedding, document_id(source_type, source_id))
    if row is None:
        return
    db.session.delete(row)
    db.session.commit()


def ensure_proposal_index() -> int:
    from models.submission import TalkSubmission

    indexed = {
        row.source_id
        for row in TalkEmbedding.query.filter_by(source_type="proposal").all()
    }
    added = 0
    for submission in TalkSubmission.query.all():
        if submission.id in indexed:
            continue
        index_talk_proposal(submission)
        added += 1
    return added


def ensure_event_index() -> int:
    from models.event import Event
    from services.scheduling import APPROVED_STATUSES

    indexed = {
        row.source_id
        for row in TalkEmbedding.query.filter_by(source_type="event").all()
    }
    added = 0
    events = Event.query.filter(Event.status.in_(APPROVED_STATUSES)).all()
    for event in events:
        if event.id in indexed:
            continue
        index_official_event(event)
        added += 1
    return added


def search_similar(
    query: str,
    limit: int = 5,
    source_types: tuple[str, ...] | None = None,
    exclude_source_id: str | None = None,
    backfill: bool = True,
) -> list[dict[str, Any]]:
    cleaned = (query or "").strip()
    if not cleaned:
        return []
    types = set(source_types) if source_types else None
    if backfill and (types is None or "proposal" in types):
        ensure_proposal_index()
    if backfill and (types is None or "event" in types):
        ensure_event_index()
    query_vector = embed_text(cleaned)
    rows = TalkEmbedding.query.all()
    hits: list[dict[str, Any]] = []
    allowed = set(source_types) if source_types else None
    for row in rows:
        if allowed and row.source_type not in allowed:
            continue
        if exclude_source_id and row.source_id == exclude_source_id:
            continue
        vector = row.embedding or []
        score = cosine_similarity(query_vector, vector)
        extra = row.extra or {}
        hits.append(
            {
                "id": row.source_id,
                "source_type": row.source_type,
                "score": round(float(score), 4),
                "title": extra.get("title") or extra.get("speaker_name") or row.source_id,
                "abstract": extra.get("abstract") or "",
                "category": extra.get("category") or "",
                "speaker_id": extra.get("speaker_id") or (row.source_id if row.source_type == "speaker" else ""),
                "speaker_name": extra.get("speaker_name") or "",
                "status": extra.get("status") or "",
                "event_id": extra.get("event_id"),
            }
        )
    hits.sort(key=lambda item: item["score"], reverse=True)
    return [item for item in hits if item["score"] > 0][: max(1, int(limit))]


PROGRAM_TALK_STATUSES = {
    "pending_assessment",
    "pending",
    "under_review",
    "approved",
    "active",
    "awaiting_speaker_confirmation",
}


def compare_against_program(
    query: str,
    exclude_source_id: str | None = None,
    backfill: bool = False,
) -> list[dict[str, Any]]:
    """Score a proposal against every approved or pending talk in the vector store."""
    hits = search_similar(
        query,
        limit=1000,
        source_types=("proposal", "event"),
        exclude_source_id=exclude_source_id,
        backfill=backfill,
    )
    comparable: list[dict[str, Any]] = []
    for hit in hits:
        status = str(hit.get("status") or "").strip().lower()
        source_type = hit.get("source_type")
        if source_type == "event" and status and status not in {"approved", "active"}:
            continue
        if source_type == "proposal" and status and status not in PROGRAM_TALK_STATUSES:
            continue
        comparable.append(hit)
    return comparable
