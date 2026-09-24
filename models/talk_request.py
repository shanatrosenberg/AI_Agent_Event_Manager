from typing import Any

from extensions import db
from services.scheduling import hall_label


class TalkRequest(db.Model):
    """An invitation from the single organizer asking a speaker to present a topic."""

    __tablename__ = "talk_requests"

    id = db.Column(db.String(36), primary_key=True)
    organizer_id = db.Column(db.String(64), db.ForeignKey("organizers.id"), nullable=False)
    speaker_id = db.Column(db.String(64), db.ForeignKey("speakers.id"), nullable=False)
    topic = db.Column(db.String(255), nullable=False)
    details = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(128), nullable=False, default="invitation")
    date = db.Column(db.String(64), nullable=True)
    start_time = db.Column(db.String(8), nullable=True)
    end_time = db.Column(db.String(8), nullable=True)
    capacity = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="pending")
    submission_id = db.Column(db.String(36), nullable=True)
    event_id = db.Column(db.String(36), nullable=True)

    speaker = db.relationship("Speaker", back_populates="talk_requests")

    def to_dict(self) -> dict[str, Any]:
        speaker_name = self.speaker.name if self.speaker and self.speaker.name else None
        return {
            "id": self.id,
            "organizer_id": self.organizer_id,
            "speaker_id": self.speaker_id,
            "speaker_name": speaker_name or self.speaker_id,
            "topic": self.topic,
            "details": self.details,
            "category": self.category,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "capacity": self.capacity,
            "hall_label": hall_label(self.capacity) if self.capacity else None,
            "status": self.status,
            "submission_id": self.submission_id,
            "event_id": self.event_id,
        }
