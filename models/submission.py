from datetime import datetime, timedelta, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

from extensions import db
from services.scheduling import hall_label

STATUS_LABELS = {
    "pending_assessment": "Pending",
    "pending": "Pending",
    "under_review": "Reviewed by AI",
    "approved": "Approved",
    "rejected": "Not approved",
}
PENDING_STATUSES = ("pending_assessment", "pending", "under_review")
TRASH_RETENTION_DAYS = 7
DEFAULT_REJECTION_MESSAGE = "Your talk proposal was not approved by the event organizer."


class TalkSubmission(db.Model):
    __tablename__ = "talk_submissions"

    id = db.Column(db.String(36), primary_key=True)
    speaker_id = db.Column(db.String(64), db.ForeignKey("speakers.id"), nullable=False)
    organizer_id = db.Column(db.String(64), db.ForeignKey("organizers.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    abstract = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(128), nullable=False)
    date = db.Column(db.String(64), nullable=True)
    start_time = db.Column(db.String(8), nullable=True)
    end_time = db.Column(db.String(8), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(64), nullable=False)
    ai_assessment = db.Column(db.JSON, nullable=False, default=dict)
    event_id = db.Column(db.String(36), nullable=True)
    rejected_at = db.Column(db.DateTime, nullable=True)
    rejection_message = db.Column(db.Text, nullable=True)

    speaker = db.relationship("Speaker", back_populates="submissions")

    @property
    def display_status(self) -> str:
        return STATUS_LABELS.get(self.status, self.status.replace("_", " ").title())

    @property
    def is_pending(self) -> bool:
        return self.status in PENDING_STATUSES

    @property
    def expires_at(self) -> datetime | None:
        if self.status != "rejected" or self.rejected_at is None:
            return None
        return self.rejected_at + timedelta(days=TRASH_RETENTION_DAYS)

    @property
    def days_remaining(self) -> int | None:
        expires = self.expires_at
        if expires is None:
            return None
        remaining = expires - utc_now()
        return max(0, remaining.days + (1 if remaining.seconds or remaining.microseconds else 0))

    @property
    def is_expired(self) -> bool:
        expires = self.expires_at
        return expires is not None and expires <= utc_now()

    def to_dict(self) -> dict[str, Any]:
        speaker_name = self.speaker.name if self.speaker and self.speaker.name else None
        expires = self.expires_at
        return {
            "id": self.id,
            "speaker_id": self.speaker_id,
            "speaker_name": speaker_name or self.speaker_id,
            "organizer_id": self.organizer_id,
            "title": self.title,
            "abstract": self.abstract,
            "category": self.category,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "capacity": self.capacity,
            "hall_label": hall_label(self.capacity) if self.capacity else None,
            "status": self.status,
            "display_status": self.display_status,
            "ai_assessment": self.ai_assessment or {},
            "event_id": self.event_id,
            "rejected_at": self.rejected_at.isoformat(timespec="seconds") if self.rejected_at else None,
            "rejection_message": self.rejection_message,
            "notification": self.rejection_message if self.status == "rejected" else None,
            "expires_at": expires.isoformat(timespec="seconds") if expires else None,
            "days_remaining": self.days_remaining,
        }
