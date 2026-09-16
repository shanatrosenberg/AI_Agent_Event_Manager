from dataclasses import dataclass
from uuid import uuid4

from models.booking import Booking
from models.event import Event
from models.submission import TalkSubmission
from cqrs.errors import DomainError
from cqrs.store import EventStore
from services.ai_assessment import AIAssessmentAgent


@dataclass
class CreateEventCommand:
    organizer_id: str
    title: str
    description: str
    date: str
    capacity: int


class CreateEventHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: CreateEventCommand) -> Event:
        event = Event(
            id=str(uuid4()),
            organizer_id=command.organizer_id,
            title=command.title,
            description=command.description,
            date=command.date,
            capacity=command.capacity,
        )
        self._store.append("EventCreated", event.to_dict())
        self._store.save_read_model(event)
        return event


@dataclass
class SubmitTalkCommand:
    speaker_id: str
    title: str
    abstract: str
    category: str


class SubmitTalkHandler:
    def __init__(self, store: EventStore, assessor: AIAssessmentAgent | None = None) -> None:
        self._store = store
        self._assessor = assessor or AIAssessmentAgent()

    def handle(self, command: SubmitTalkCommand) -> TalkSubmission:
        submission = TalkSubmission(
            id=str(uuid4()),
            speaker_id=command.speaker_id,
            title=command.title,
            abstract=command.abstract,
            category=command.category,
            status="pending_assessment",
            ai_assessment={},
        )
        self._store.append("TalkSubmitted", submission.to_dict())

        assessment = self._assessor.enqueue(submission)
        submission.ai_assessment = assessment
        submission.status = "under_review"
        self._store.append("TalkQueuedForAssessment", submission.to_dict())
        self._store.save_submission(submission)
        return submission


@dataclass
class RegisterAttendeeCommand:
    attendee_id: str
    event_id: str
    seats: int = 1


class RegisterAttendeeHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: RegisterAttendeeCommand) -> Booking:
        event = self._store.get_event(command.event_id)
        if event is None:
            raise DomainError("event not found", status=404)

        if event.status != "active":
            raise DomainError("event is not active", status=409)

        if self._store.has_booking(command.attendee_id, command.event_id):
            raise DomainError("attendee is already registered for this event", status=409)

        if command.seats > event.remaining_seats:
            raise DomainError(
                f"not enough seats remaining ({event.remaining_seats} available)",
                status=409,
            )

        event.seats_booked += command.seats
        self._store.save_read_model(event)
        self._store.append(
            "SeatReserved",
            {
                "event_id": event.id,
                "attendee_id": command.attendee_id,
                "seats": command.seats,
                "seats_booked": event.seats_booked,
                "remaining_seats": event.remaining_seats,
            },
        )

        booking = Booking(
            id=str(uuid4()),
            attendee_id=command.attendee_id,
            event_id=command.event_id,
            seats=command.seats,
            status="confirmed",
        )
        self._store.append("AttendeeRegistered", booking.to_dict())
        self._store.save_booking(booking)
        return booking
