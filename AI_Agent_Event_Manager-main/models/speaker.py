from extensions import db
from models.password import HasPassword


class Speaker(HasPassword, db.Model):
    __tablename__ = "speakers"

    id = db.Column(db.String(64), primary_key=True)
    name = db.Column(db.String(255), nullable=True)

    submissions = db.relationship("TalkSubmission", back_populates="speaker", lazy=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name}
