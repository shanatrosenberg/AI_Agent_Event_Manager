from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.organizer import Organizer
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import PENDING_STATUSES, TalkSubmission, utc_now
from models.talk_request import TalkRequest
from extensions import db
from services.auth import ROLE_MODELS, create_account, find_account, get_account
from services.scheduling import APPROVED_STATUSES, BOOKABLE_STATUSES, clocks_overlap


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

    def get_account(self, role: str, user_id: str):
        return get_account(role, user_id)

    def find_account(self, role: str, identifier: str):
        return find_account(role, identifier)

    def create_account(self, role: str, user_id: str, name: str | None = None):
        if role not in ROLE_MODELS:
            raise ValueError(f"unsupported role: {role}")
        account = create_account(role, user_id, name)
        db.session.add(account)
        db.session.flush()
        return account

    def save_account(self, account) -> None:
        db.session.add(account)
        self._commit()

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

    def get_submission(self, submission_id: str) -> TalkSubmission | None:
        return db.session.get(TalkSubmission, submission_id)

    def _organizer_submissions(self, organizer_id: str):
        return TalkSubmission.query.filter(
            db.or_(
                TalkSubmission.organizer_id == organizer_id,
                TalkSubmission.organizer_id.is_(None),
            )
        )

    def list_submissions_for_organizer(self, organizer_id: str) -> list[TalkSubmission]:
        return self._organizer_submissions(organizer_id).order_by(TalkSubmission.title.asc()).all()

    def list_pending_submissions(self, organizer_id: str) -> list[TalkSubmission]:
        return (
            self._organizer_submissions(organizer_id)
            .filter(TalkSubmission.status.in_(PENDING_STATUSES))
            .order_by(TalkSubmission.title.asc())
            .all()
        )

    def list_rejected_submissions(self, organizer_id: str) -> list[TalkSubmission]:
        self.purge_expired_rejections()
        rows = (
            self._organizer_submissions(organizer_id)
            .filter(TalkSubmission.status == "rejected")
            .order_by(TalkSubmission.rejected_at.desc())
            .all()
        )
        return [row for row in rows if not row.is_expired]

    def purge_expired_rejections(self) -> int:
        expired = [
            row
            for row in TalkSubmission.query.filter(TalkSubmission.status == "rejected").all()
            if row.is_expired
        ]
        for row in expired:
            self.append(
                "TalkPurged",
                {"id": row.id, "title": row.title, "purged_at": utc_now().isoformat(timespec="seconds")},
            )
            db.session.delete(row)
        if expired:
            self._commit()
        return len(expired)

    def delete_submission(self, submission: TalkSubmission) -> None:
        db.session.delete(submission)
        self._commit()

    def delete_event(self, event: Event) -> None:
        Booking.query.filter_by(event_id=event.id).delete()
        db.session.delete(event)
        self._commit()

    def save_talk_request(self, talk_request: TalkRequest) -> None:
        db.session.add(talk_request)
        self._commit()

    def get_talk_request(self, request_id: str) -> TalkRequest | None:
        return db.session.get(TalkRequest, request_id)

    def list_requests_for_speaker(self, speaker_id: str) -> list[TalkRequest]:
        return TalkRequest.query.filter_by(speaker_id=speaker_id).all()

    def list_requests_for_organizer(self, organizer_id: str) -> list[TalkRequest]:
        return TalkRequest.query.filter_by(organizer_id=organizer_id).all()

    def get_speaker(self, speaker_id: str) -> Speaker | None:
        return db.session.get(Speaker, speaker_id)

    def list_speakers(self) -> list[Speaker]:
        return Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all()

    def get_event(self, event_id: str) -> Event | None:
        return db.session.get(Event, event_id)

    def list_active_events(self) -> list[Event]:
        events = Event.query.filter(Event.status.in_(BOOKABLE_STATUSES)).all()
        return [event for event in events if event.remaining_seats > 0]

    def list_approved_events(self) -> list[Event]:
        return (
            Event.query.filter(Event.status.in_(APPROVED_STATUSES))
            .order_by(Event.date.asc(), Event.start_time.asc(), Event.title.asc())
            .all()
        )

    def find_hall_conflict(
        self,
        capacity: int,
        date: str,
        start_time: str,
        end_time: str,
        exclude_event_id: str | None = None,
    ) -> Event | None:
        query = Event.query.filter(
            Event.capacity == capacity,
            Event.date == date,
            Event.status.in_(BOOKABLE_STATUSES),
        )
        if exclude_event_id:
            query = query.filter(Event.id != exclude_event_id)
        for event in query.all():
            if not event.start_time or not event.end_time:
                continue
            if clocks_overlap(start_time, end_time, event.start_time, event.end_time):
                return event
        return None

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
