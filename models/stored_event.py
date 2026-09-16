from extensions import db


class StoredEvent(db.Model):
    """Persisted domain events for CQRS / event sourcing."""

    __tablename__ = "stored_events"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    event_name = db.Column(db.String(128), nullable=False)
    payload = db.Column(db.JSON, nullable=False, default=dict)
