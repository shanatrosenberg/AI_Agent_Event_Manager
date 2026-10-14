from datetime import datetime, timezone
from typing import Any

from extensions import db


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class WaitlistEntry(db.Model):
    __tablename__ = "waitlist_entries"

    id = db.Column(db.String(36), primary_key=True)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False, index=True)
    attendee_id = db.Column(db.String(64), db.ForeignKey("attendees.id"), nullable=False, index=True)
    seats_requested = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(32), nullable=False, default="waiting")
    created_at = db.Column(db.DateTime, nullable=False, default=_utc_now)
    notified_at = db.Column(db.DateTime, nullable=True)
    offer_seats = db.Column(db.Integer, nullable=True)
    claimed_seats = db.Column(db.Integer, nullable=False, default=0)

    event = db.relationship("Event")
    attendee = db.relationship("Attendee")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "attendee_id": self.attendee_id,
            "seats_requested": self.seats_requested,
            "status": self.status,
            "offer_seats": self.offer_seats,
            "claimed_seats": self.claimed_seats,
        }
