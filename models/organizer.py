from extensions import db


class Organizer(db.Model):
    __tablename__ = "organizers"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=True)

    events = db.relationship("Event", back_populates="organizer", lazy=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}
