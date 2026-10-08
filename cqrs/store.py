from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.organizer import Organizer
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import PENDING_STATUSES, TalkSubmission, utc_now
from models.talk_request import TalkRequest
from sqlalchemy import func, inspect, or_, text

from cqrs.events import infer_aggregate_id, infer_aggregate_type
from cqrs.projections import project_talk, project_talk_state
from extensions import db
from services.auth import ROLE_MODELS, create_account, find_account, get_account
from services.scheduling import APPROVED_STATUSES, BOOKABLE_STATUSES, clocks_overlap, has_occurred


def ensure_event_store_schema() -> None:
    """Add Event Sourcing metadata columns on existing Somee / SQLite stores."""
    inspector = inspect(db.engine)
    if "stored_events" not in set(inspector.get_table_names()):
        db.create_all()
        return
    columns = {column["name"] for column in inspector.get_columns("stored_events")}
    dialect = db.engine.dialect.name
    column_defs = {
        "aggregate_id": "VARCHAR(64)",
        "aggregate_type": "VARCHAR(64)",
        "occurred_at": "DATETIME",
    }
    added = False
    for column_name, column_type in column_defs.items():
        if column_name in columns:
            continue
        if dialect == "sqlite":
            db.session.execute(text(f"ALTER TABLE stored_events ADD COLUMN {column_name} {column_type}"))
        else:
            db.session.execute(text(f"ALTER TABLE stored_events ADD {column_name} {column_type} NULL"))
        added = True
    if added:
        db.session.commit()


class EventStore:
    """SQLAlchemy-backed event store and read model (CQRS / Event Sourcing)."""

    def append(
        self,
        event_name: str,
        payload: dict | None = None,
        *,
        aggregate_id: str | None = None,
        aggregate_type: str | None = None,
    ) -> StoredEvent:
        data = dict(payload or {})
        event = StoredEvent(
            event_name=event_name,
            payload=data,
            aggregate_id=aggregate_id or infer_aggregate_id(data, event_name),
            aggregate_type=aggregate_type or infer_aggregate_type(event_name, data),
            occurred_at=utc_now(),
        )
        db.session.add(event)
        return event

    def list_stored_events(
        self,
        *,
        limit: int = 200,
        event_names: tuple[str, ...] | list[str] | None = None,
        aggregate_id: str | None = None,
        newest_first: bool = True,
    ) -> list[StoredEvent]:
        query = StoredEvent.query
        names = tuple(event_names or ())
        if names:
            query = query.filter(StoredEvent.event_name.in_(names))
        value = str(aggregate_id or "").strip()
        if value:
            query = query.filter(StoredEvent.aggregate_id == value)
        order = StoredEvent.id.desc() if newest_first else StoredEvent.id.asc()
        return query.order_by(order).limit(max(1, min(int(limit or 200), 500))).all()

    def stream_for_aggregate(self, aggregate_id: str) -> list[StoredEvent]:
        value = str(aggregate_id or "").strip()
        if not value:
            return []
        rows = StoredEvent.query.order_by(StoredEvent.id.asc()).all()
        matched: list[StoredEvent] = []
        for row in rows:
            payload = row.payload if isinstance(row.payload, dict) else {}
            identifiers = {
                str(row.aggregate_id or ""),
                str(payload.get("id") or ""),
                str(payload.get("submission_id") or ""),
            }
            if value in identifiers:
                matched.append(row)
        return matched

    def project_talks(self, aggregate_id: str | None = None) -> list[dict]:
        if aggregate_id:
            events = self.stream_for_aggregate(aggregate_id)
            snapshot = project_talk(events, aggregate_id)
            return [snapshot] if snapshot else []
        events = StoredEvent.query.order_by(StoredEvent.id.asc()).all()
        talks = project_talk_state(events)
        return list(talks.values())

    def project_talk(self, submission_id: str) -> dict | None:
        events = self.stream_for_aggregate(submission_id)
        return project_talk(events, submission_id)

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
        self.purge_expired_rejections()
        return (
            Event.query.filter_by(organizer_id=organizer_id)
            .filter(Event.status.in_(APPROVED_STATUSES))
            .order_by(Event.date.asc(), Event.start_time.asc(), Event.title.asc())
            .all()
        )

    def count_attendees(self) -> int:
        return Attendee.query.count()

    def organizer_stats(self, organizer_id: str) -> dict[str, int]:
        events = self.list_by_organizer(organizer_id)
        return {
            "attendees": self.count_attendees(),
            "events_held": sum(1 for event in events if has_occurred(event.date, event.end_time)),
            "active_events": len(events),
        }

    def save_submission(self, submission: TalkSubmission) -> None:
        db.session.add(submission)
        self._commit()

    def list_submissions_by_speaker(self, speaker_id: str) -> list[TalkSubmission]:
        self.purge_expired_rejections()
        return TalkSubmission.query.filter_by(speaker_id=speaker_id).all()

    def list_speaker_initiated_submissions(self, speaker_id: str) -> list[TalkSubmission]:
        invitation_ids = {
            item.submission_id
            for item in TalkRequest.query.filter(
                TalkRequest.speaker_id == speaker_id,
                TalkRequest.submission_id.isnot(None),
            ).all()
        }
        rows = [
            row
            for row in self.list_submissions_by_speaker(speaker_id)
            if row.id not in invitation_ids
        ]
        rows.sort(key=lambda row: (row.date or "", row.start_time or "", row.title or ""))
        return rows

    def list_events_for_speaker(self, speaker_id: str) -> list[Event]:
        self.purge_expired_rejections()
        return (
            Event.query.filter_by(speaker_id=speaker_id)
            .filter(Event.status.in_(APPROVED_STATUSES))
            .order_by(Event.date.asc(), Event.start_time.asc(), Event.title.asc())
            .all()
        )

    def speaker_event_payload(self, event: Event) -> dict:
        payload = event.to_dict()
        submission = self.get_submission_by_event_id(event.id)
        payload["abstract"] = (
            (submission.abstract if submission and submission.abstract else None)
            or event.description
            or ""
        )
        return payload

    def get_submission(self, submission_id: str) -> TalkSubmission | None:
        return db.session.get(TalkSubmission, submission_id)

    def get_submission_by_event_id(self, event_id: str) -> TalkSubmission | None:
        return TalkSubmission.query.filter_by(event_id=event_id).first()

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

    def list_submissions_for_assessment(self) -> list[TalkSubmission]:
        return (
            TalkSubmission.query.filter(TalkSubmission.status.in_(PENDING_STATUSES))
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
            if row.event_id:
                event = self.get_event(row.event_id)
                if event is not None:
                    Booking.query.filter_by(event_id=event.id).delete()
                    db.session.delete(event)
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

    def list_requests_for_speaker(
        self, speaker_id: str, statuses: tuple[str, ...] | None = None
    ) -> list[TalkRequest]:
        query = TalkRequest.query.filter_by(speaker_id=speaker_id)
        if statuses:
            query = query.filter(TalkRequest.status.in_(statuses))
        return query.order_by(TalkRequest.date.asc(), TalkRequest.topic.asc()).all()

    def list_requests_for_organizer(
        self, organizer_id: str, statuses: tuple[str, ...] | None = None
    ) -> list[TalkRequest]:
        query = TalkRequest.query.filter_by(organizer_id=organizer_id)
        if statuses:
            query = query.filter(TalkRequest.status.in_(statuses))
        return query.order_by(TalkRequest.topic.asc()).all()

    def get_speaker(self, speaker_id: str) -> Speaker | None:
        return db.session.get(Speaker, speaker_id)

    def list_speakers(self) -> list[Speaker]:
        return Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all()

    def get_event(self, event_id: str) -> Event | None:
        return db.session.get(Event, event_id)

    def list_active_events(self) -> list[Event]:
        events = Event.query.filter(Event.status.in_(BOOKABLE_STATUSES)).all()
        return [event for event in events if event.remaining_seats > 0]

    def list_approved_events(self, topic: str | None = None, speaker: str | None = None) -> list[Event]:
        query = Event.query.filter(Event.status.in_(APPROVED_STATUSES))
        topic_key = (topic or "").strip().lower()
        speaker_key = (speaker or "").strip().lower()
        if topic_key:
            matching_ids = db.session.query(TalkSubmission.event_id).filter(
                TalkSubmission.event_id.isnot(None),
                func.lower(TalkSubmission.category) == topic_key,
            )
            if topic_key == "session":
                categorized_ids = db.session.query(TalkSubmission.event_id).filter(
                    TalkSubmission.event_id.isnot(None),
                    TalkSubmission.category.isnot(None),
                    func.lower(TalkSubmission.category) != "session",
                    TalkSubmission.category != "",
                )
                query = query.filter(or_(Event.id.in_(matching_ids), ~Event.id.in_(categorized_ids)))
            else:
                query = query.filter(Event.id.in_(matching_ids))
        if speaker_key:
            query = query.outerjoin(Speaker, Event.speaker_id == Speaker.id).filter(
                or_(
                    func.lower(Event.speaker_id) == speaker_key,
                    func.lower(Speaker.id) == speaker_key,
                    func.lower(Speaker.name) == speaker_key,
                )
            )
        return query.order_by(Event.date.asc(), Event.start_time.asc(), Event.title.asc()).all()

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

    def list_bookings_for_attendee(self, attendee_id: str) -> list[Booking]:
        return (
            Booking.query.filter_by(attendee_id=attendee_id, status="confirmed")
            .join(Event, Booking.event_id == Event.id)
            .order_by(Event.date.asc(), Event.start_time.asc(), Event.title.asc())
            .all()
        )

    @staticmethod
    def _commit() -> None:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
