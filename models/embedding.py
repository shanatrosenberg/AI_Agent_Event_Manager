from datetime import datetime, timezone
from typing import Any

from extensions import db


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class TalkEmbedding(db.Model):
    """Persisted vector for a talk proposal or speaker profile (Somee JSON storage)."""

    __tablename__ = "talk_embeddings"

    id = db.Column(db.String(96), primary_key=True)
    source_type = db.Column(db.String(32), nullable=False, index=True)
    source_id = db.Column(db.String(64), nullable=False, index=True)
    content_hash = db.Column(db.String(64), nullable=False)
    document_text = db.Column(db.Text, nullable=False)
    embedding = db.Column(db.JSON, nullable=False, default=list)
    extra = db.Column(db.JSON, nullable=False, default=dict)
    updated_at = db.Column(db.DateTime, nullable=False, default=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "content_hash": self.content_hash,
            "document_text": self.document_text,
            "extra": self.extra or {},
            "updated_at": self.updated_at.isoformat(timespec="seconds") if self.updated_at else None,
        }
