from dataclasses import dataclass

from models.event import Event
from models.speaker import Speaker
from models.submission import TalkSubmission
from models.talk_request import TalkRequest
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


class ListSpeakerSubmissionsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakerSubmissionsQuery) -> list[TalkSubmission]:
        return self._store.list_submissions_by_speaker(query.speaker_id)


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


class ListSpeakerRequestsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListSpeakerRequestsQuery) -> list[TalkRequest]:
        return self._store.list_requests_for_speaker(query.speaker_id)


@dataclass
class ListOrganizerRequestsQuery:
    organizer_id: str


class ListOrganizerRequestsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListOrganizerRequestsQuery) -> list[TalkRequest]:
        return self._store.list_requests_for_organizer(query.organizer_id)


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
class ListApprovedEventsQuery:
    pass


class ListApprovedEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListApprovedEventsQuery) -> list[Event]:
        return self._store.list_approved_events()
