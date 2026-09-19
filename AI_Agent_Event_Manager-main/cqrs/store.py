from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.organizer import Organizer
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import TalkSubmission
from extensions import db


class EventStore:
    """SQLAlchemy-backed event store and read model (CQRS / Event Sourcing)."""

    def append(self, event_name: str, payload: dict) -> None:
        db.session.add(StoredEvent(event_name=event_name, payload=payload))

    def ensure_organizer(self, organizer_id: str) -> Organizer:
        organizer = db.session.get(Organizer, organizer_id)
        if organizer is None:
            organizer = Organizer(id=organizer_id)
            db.session.add(organizer)
            db.session.flush()
        return organizer

    def ensure_speaker(self, speaker_id: str) -> Speaker:
        speaker = db.session.get(Speaker, speaker_id)
        if speaker is None:
            speaker = Speaker(id=speaker_id)
            db.session.add(speaker)
            db.session.flush()
        return speaker

    def ensure_attendee(self, attendee_id: str) -> Attendee:
        attendee = db.session.get(Attendee, attendee_id)
        if attendee is None:
            attendee = Attendee(id=attendee_id)
            db.session.add(attendee)
            db.session.flush()
        return attendee

    def save_read_model(self, event: Event) -> None:
        db.session.add(event)
        self._commit()

    def list_by_organizer(self, organizer_id: str) -> list[Event]:
        return Event.query.filter_by(organizer_id=organizer_id).all()

    def save_submission(self, submission: TalkSubmission) -> None:
        db.session.add(submission)
        self._commit()

    def list_submissions_by_speaker(self, speaker_id: str) -> list[TalkSubmission]:
        return TalkSubmission.query.filter_by(speaker_id=speaker_id).all()

    def get_event(self, event_id: str) -> Event | None:
        return db.session.get(Event, event_id)

    def list_active_events(self) -> list[Event]:
        events = Event.query.filter_by(status="active").all()
        return [event for event in events if event.remaining_seats > 0]

    def save_booking(self, booking: Booking) -> None:
        db.session.add(booking)
        self._commit()

    def has_booking(self, attendee_id: str, event_id: str) -> bool:
        return (
            Booking.query.filter_by(
                attendee_id=attendee_id,
                event_id=event_id,
                status="confirmed",
            ).first()
            is not None
        )

    @staticmethod
    def _commit() -> None:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
