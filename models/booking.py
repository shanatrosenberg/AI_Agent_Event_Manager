from extensions import db


class Booking(db.Model):
    __tablename__ = "bookings"

    id = db.Column(db.String(36), primary_key=True)
    attendee_id = db.Column(db.String(64), db.ForeignKey("attendees.id"), nullable=False)
    event_id = db.Column(db.String(36), db.ForeignKey("events.id"), nullable=False)
    seats = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(32), nullable=False, default="confirmed")

    attendee = db.relationship("Attendee", back_populates="bookings")
    event = db.relationship("Event", back_populates="bookings")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "attendee_id": self.attendee_id,
            "event_id": self.event_id,
            "seats": self.seats,
            "status": self.status,
        }
