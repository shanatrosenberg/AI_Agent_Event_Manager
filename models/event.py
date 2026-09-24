from typing import Any

from extensions import db
from services.scheduling import APPROVED_STATUSES, BOOKABLE_STATUSES, hall_label


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.String(36), primary_key=True)
    organizer_id = db.Column(db.String(64), db.ForeignKey("organizers.id"), nullable=False)
    speaker_id = db.Column(db.String(64), db.ForeignKey("speakers.id"), nullable=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    date = db.Column(db.String(64), nullable=False)
    start_time = db.Column(db.String(8), nullable=True)
    end_time = db.Column(db.String(8), nullable=True)
    capacity = db.Column(db.Integer, nullable=False)
    seats_booked = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="approved")

    organizer = db.relationship("Organizer", back_populates="events")
    speaker = db.relationship("Speaker", back_populates="events")
    bookings = db.relationship("Booking", back_populates="event", lazy=True)

    @property
    def remaining_seats(self) -> int:
        booked = self.seats_booked or 0
        capacity = self.capacity or 0
        return max(0, capacity - booked)

    @property
    def hall_label(self) -> str:
        return hall_label(self.capacity)

    @property
    def is_approved(self) -> bool:
        return self.status in APPROVED_STATUSES

    @property
    def is_bookable(self) -> bool:
        return self.status in BOOKABLE_STATUSES and self.remaining_seats > 0

    def to_dict(self) -> dict[str, Any]:
        speaker_name = self.speaker.name if self.speaker and self.speaker.name else None
        return {
            "id": self.id,
            "organizer_id": self.organizer_id,
            "speaker_id": self.speaker_id,
            "speaker_name": speaker_name or self.speaker_id,
            "title": self.title,
            "description": self.description,
            "date": self.date,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "capacity": self.capacity,
            "hall_label": self.hall_label,
            "seats_booked": self.seats_booked,
            "status": self.status,
            "display_status": "Approved" if self.is_approved else (self.status or "unknown").replace("_", " ").title(),
            "remaining_seats": self.remaining_seats,
            "available": self.is_bookable,
        }
