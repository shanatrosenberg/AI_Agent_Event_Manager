from datetime import datetime, timezone

from extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Topic(db.Model):
    """A reusable talk category created by the organizer and selected by lecturers and attendees."""

    __tablename__ = "topics"

    slug = db.Column(db.String(128), primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    def to_dict(self) -> dict[str, str]:
        return {"slug": self.slug, "name": self.name, "id": self.slug}
