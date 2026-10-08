from dataclasses import dataclass

from models.event import Event
from models.speaker import Speaker
from models.submission import TalkSubmission
from models.talk_request import TalkRequest
from cqrs.events import EVENT_ALIASES
from cqrs.store import EventStore


@dataclass
class ListOrganizerEventsQuery:
    organizer_id: str


class ListOrganizerEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListOrganizerEventsQuery) -> list[Event]:
        return self._store.list_by_organizer(query.organizer_id)


@dataclass
class ListSpeakerSubmissionsQuery:
    speaker_id: str
    initiated_only: bool = False


class ListSpeakerSubmissionsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakerSubmissionsQuery) -> list[TalkSubmission]:
        if query.initiated_only:
            return self._store.list_speaker_initiated_submissions(query.speaker_id)
        return self._store.list_submissions_by_speaker(query.speaker_id)


@dataclass
class ListSpeakerEventsQuery:
    speaker_id: str


class ListSpeakerEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakerEventsQuery) -> list[Event]:
        return self._store.list_events_for_speaker(query.speaker_id)


@dataclass
class ListSpeakersQuery:
    pass


class ListSpeakersHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakersQuery) -> list[Speaker]:
        return self._store.list_speakers()


@dataclass
class ListSpeakerRequestsQuery:
    speaker_id: str
    statuses: tuple[str, ...] | None = None


class ListSpeakerRequestsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakerRequestsQuery) -> list[TalkRequest]:
        return self._store.list_requests_for_speaker(query.speaker_id, query.statuses)


@dataclass
class ListOrganizerRequestsQuery:
    organizer_id: str
    statuses: tuple[str, ...] | None = None


class ListOrganizerRequestsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListOrganizerRequestsQuery) -> list[TalkRequest]:
        return self._store.list_requests_for_organizer(query.organizer_id, query.statuses)


@dataclass
class ListOrganizerSubmissionsQuery:
    organizer_id: str


class ListOrganizerSubmissionsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListOrganizerSubmissionsQuery) -> list[TalkSubmission]:
        return self._store.list_submissions_for_organizer(query.organizer_id)


@dataclass
class ListPendingProposalsQuery:
    organizer_id: str


class ListPendingProposalsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListPendingProposalsQuery) -> list[TalkSubmission]:
        return self._store.list_pending_submissions(query.organizer_id)


@dataclass
class ListTrashQuery:
    organizer_id: str


class ListTrashHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListTrashQuery) -> list[TalkSubmission]:
        return self._store.list_rejected_submissions(query.organizer_id)


@dataclass
class ListActiveEventsQuery:
    pass


class ListActiveEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListActiveEventsQuery) -> list[Event]:
        return self._store.list_active_events()


@dataclass
class ListAttendeeTicketsQuery:
    attendee_id: str


class ListAttendeeTicketsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListAttendeeTicketsQuery) -> list:
        return self._store.list_bookings_for_attendee(query.attendee_id)


@dataclass
class ListApprovedEventsQuery:
    topic: str | None = None
    speaker: str | None = None


class ListApprovedEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListApprovedEventsQuery) -> list[Event]:
        return self._store.list_approved_events(topic=query.topic, speaker=query.speaker)


@dataclass
class OrganizerStatsQuery:
    organizer_id: str


class OrganizerStatsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: OrganizerStatsQuery) -> dict[str, int]:
        return self._store.organizer_stats(query.organizer_id)


@dataclass
class SemanticSearchQuery:
    query: str
    limit: int = 5
    source_types: tuple[str, ...] | None = None
    exclude_source_id: str | None = None


@dataclass
class ListEventLogQuery:
    limit: int = 200
    event_name: str | None = None
    aggregate_id: str | None = None


class ListEventLogHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListEventLogQuery) -> list[dict]:
        names = None
        event_name = (query.event_name or "").strip()
        if event_name:
            aliases = [key for key, value in EVENT_ALIASES.items() if value == event_name]
            names = tuple({event_name, *aliases})
        try:
            limit = int(query.limit or 200)
        except (TypeError, ValueError):
            limit = 200
        rows = self._store.list_stored_events(
            limit=limit,
            event_names=names,
            aggregate_id=(query.aggregate_id or "").strip() or None,
            newest_first=True,
        )
        return [row.to_audit_dict() for row in rows]


@dataclass
class ProjectTalksQuery:
    submission_id: str | None = None


class ProjectTalksHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ProjectTalksQuery) -> list[dict]:
        return self._store.project_talks(aggregate_id=(query.submission_id or "").strip() or None)


class SemanticSearchHandler:
    def handle(self, query: SemanticSearchQuery) -> list[dict]:
        from cqrs.errors import DomainError
        from services.vector_store import search_similar

        text = (query.query or "").strip()
        if not text:
            raise DomainError("query is required")
        try:
            limit = int(query.limit or 5)
        except (TypeError, ValueError):
            limit = 5
        limit = min(20, max(1, limit))
        return search_similar(
            text,
            limit=limit,
            source_types=query.source_types,
            exclude_source_id=query.exclude_source_id,
        )
