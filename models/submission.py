from typing import Any

from extensions import db


class TalkSubmission(db.Model):
    __tablename__ = "talk_submissions"

    id = db.Column(db.String(36), primary_key=True)
    speaker_id = db.Column(db.String(64), db.ForeignKey("speakers.id"), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    abstract = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(128), nullable=False)
    status = db.Column(db.String(64), nullable=False)
    ai_assessment = db.Column(db.JSON, nullable=False, default=dict)

    speaker = db.relationship("Speaker", back_populates="submissions")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "speaker_id": self.speaker_id,
            "title": self.title,
            "abstract": self.abstract,
            "category": self.category,
            "status": self.status,
            "ai_assessment": self.ai_assessment or {},
        }
