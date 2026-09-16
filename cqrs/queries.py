from dataclasses import dataclass

from models.event import Event
from models.submission import TalkSubmission
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
class ListActiveEventsQuery:
    pass


class ListActiveEventsHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, query: ListActiveEventsQuery) -> list[Event]:
        return self._store.list_active_events()
