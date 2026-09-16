from models.booking import Booking
from models.event import Event
from models.submission import TalkSubmission


class EventStore:
    """In-memory event store and read model (CQRS / Event Sourcing)."""

    def __init__(self) -> None:
        self._events: list[dict] = []
        self._read_model: dict[str, Event] = {}
        self._submission_read_model: dict[str, TalkSubmission] = {}
        self._booking_read_model: dict[str, Booking] = {}

    def append(self, event_name: str, payload: dict) -> None:
        self._events.append({"event": event_name, "payload": payload})

    def save_read_model(self, event: Event) -> None:
        self._read_model[event.id] = event

    def list_by_organizer(self, organizer_id: str) -> list[Event]:
        return [
            event
            for event in self._read_model.values()
            if event.organizer_id == organizer_id
        ]

    def save_submission(self, submission: TalkSubmission) -> None:
        self._submission_read_model[submission.id] = submission

    def list_submissions_by_speaker(self, speaker_id: str) -> list[TalkSubmission]:
        return [
            submission
            for submission in self._submission_read_model.values()
            if submission.speaker_id == speaker_id
        ]

    def get_event(self, event_id: str) -> Event | None:
        return self._read_model.get(event_id)

    def list_active_events(self) -> list[Event]:
        return [
            event
            for event in self._read_model.values()
            if event.status == "active" and event.remaining_seats > 0
        ]

    def save_booking(self, booking: Booking) -> None:
        self._booking_read_model[booking.id] = booking

    def has_booking(self, attendee_id: str, event_id: str) -> bool:
        return any(
            booking.attendee_id == attendee_id
            and booking.event_id == event_id
            and booking.status == "confirmed"
            for booking in self._booking_read_model.values()
        )
