from datetime import datetime
from typing import Any

from extensions import db


class StoredEvent(db.Model):
    """Append-only domain event for CQRS / Event Sourcing."""

    __tablename__ = "stored_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_name = db.Column(db.String(128), nullable=False)
    payload = db.Column(db.JSON, nullable=False, default=dict)
    aggregate_id = db.Column(db.String(64), nullable=True, index=True)
    aggregate_type = db.Column(db.String(64), nullable=True, index=True)
    occurred_at = db.Column(db.DateTime, nullable=True)

    def to_audit_dict(self) -> dict[str, Any]:
        from cqrs.events import canonicalize, event_label, event_summary

        payload = self.payload if isinstance(self.payload, dict) else {}
        occurred = self.occurred_at
        return {
            "id": self.id,
            "event_name": self.event_name,
            "canonical_name": canonicalize(self.event_name),
            "label": event_label(self.event_name),
            "occurred_at": occurred.isoformat(timespec="seconds") if isinstance(occurred, datetime) else None,
            "aggregate_id": self.aggregate_id or payload.get("id") or payload.get("submission_id"),
            "aggregate_type": self.aggregate_type,
            "title": payload.get("title") or payload.get("topic"),
            "speaker_id": payload.get("speaker_id"),
            "speaker_name": payload.get("speaker_name"),
            "status": payload.get("status"),
            "summary": event_summary(self.event_name, payload),
            "payload": payload,
        }
