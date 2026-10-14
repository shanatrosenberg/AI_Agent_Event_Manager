from datetime import datetime, timezone
from typing import Any

from extensions import db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.String(36), primary_key=True)
    recipient_id = db.Column(db.String(64), nullable=False, index=True)
    recipient_role = db.Column(db.String(32), nullable=False, index=True)
    sender_id = db.Column(db.String(64), nullable=True, index=True)
    sender_role = db.Column(db.String(32), nullable=True)
    subject = db.Column(db.String(255), nullable=True)
    parent_id = db.Column(db.String(36), nullable=True, index=True)
    event_id = db.Column(db.String(36), nullable=True, index=True)
    kind = db.Column(db.String(32), nullable=False, default="event_cancelled")
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    read_at = db.Column(db.DateTime, nullable=True)

    def to_dict(
        self,
        viewer_id: str | None = None,
        viewer_role: str | None = None,
    ) -> dict[str, Any]:
        created = self.created_at.isoformat(sep=" ", timespec="minutes") if self.created_at else ""
        sender_role = (self.sender_role or "").strip().lower()
        viewer = (viewer_id or "").strip()
        viewer_role = (viewer_role or "").strip().lower()
        inbound = self.recipient_id == viewer and (not viewer_role or self.recipient_role == viewer_role)
        if viewer and self.sender_id == viewer and (not viewer_role or sender_role == viewer_role):
            from_label = "You"
        elif sender_role == "organizer" or (not sender_role and self.kind == "event_cancelled"):
            from_label = "Event Organizer"
        elif sender_role == "speaker":
            from_label = "Lecturer"
        else:
            from_label = "Smart Events"
        unread = (inbound and self.read_at is None) if viewer else self.read_at is None
        return {
            "id": self.id,
            "recipient_id": self.recipient_id,
            "recipient_role": self.recipient_role,
            "sender_id": self.sender_id,
            "sender_role": self.sender_role,
            "from_label": from_label,
            "subject": self.subject
            or (
                "Event cancelled"
                if self.kind == "event_cancelled"
                else "Seats available"
                if self.kind == "waitlist_offer"
                else "Message"
            ),
            "parent_id": self.parent_id,
            "event_id": self.event_id,
            "kind": self.kind,
            "body": self.body,
            "created_at": created,
            "read": not unread,
            "unread": unread,
        }
