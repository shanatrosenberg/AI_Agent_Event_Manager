from extensions import db


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.String(36), primary_key=True)
    organizer_id = db.Column(db.String(64), db.ForeignKey("organizers.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    date = db.Column(db.String(64), nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    seats_booked = db.Column(db.Integer, nullable=False, default=0)
    status = db.Column(db.String(32), nullable=False, default="active")

    organizer = db.relationship("Organizer", back_populates="events")
    bookings = db.relationship("Booking", back_populates="event", lazy=True)

    @property
    def remaining_seats(self) -> int:
        booked = self.seats_booked or 0
        capacity = self.capacity or 0
        return max(0, capacity - booked)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organizer_id": self.organizer_id,
            "title": self.title,
            "description": self.description,
            "date": self.date,
            "capacity": self.capacity,
            "seats_booked": self.seats_booked,
            "status": self.status,
            "remaining_seats": self.remaining_seats,
            "available": self.status == "active" and self.remaining_seats > 0,
        }
