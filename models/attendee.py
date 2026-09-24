from extensions import db
from models.password import HasPassword


class Attendee(HasPassword, db.Model):
    __tablename__ = "attendees"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=True)

    bookings = db.relationship("Booking", back_populates="attendee", lazy=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}
