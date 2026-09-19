from cqrs.commands import (
    CreateEventCommand,
    CreateEventHandler,
    RegisterAttendeeCommand,
    RegisterAttendeeHandler,
    SubmitTalkCommand,
    SubmitTalkHandler,
)
from cqrs.queries import (
    ListActiveEventsHandler,
    ListActiveEventsQuery,
    ListOrganizerEventsHandler,
    ListOrganizerEventsQuery,
    ListSpeakerSubmissionsHandler,
    ListSpeakerSubmissionsQuery,
)
from cqrs.store import EventStore
from services.ai_assessment import AIAssessmentAgent

event_store = EventStore()
ai_assessment_agent = AIAssessmentAgent()
create_event_handler = CreateEventHandler(event_store)
list_organizer_events_handler = ListOrganizerEventsHandler(event_store)
submit_talk_handler = SubmitTalkHandler(event_store, ai_assessment_agent)
list_speaker_submissions_handler = ListSpeakerSubmissionsHandler(event_store)
list_active_events_handler = ListActiveEventsHandler(event_store)
register_attendee_handler = RegisterAttendeeHandler(event_store)

__all__ = [
    "CreateEventCommand",
    "CreateEventHandler",
    "ListActiveEventsHandler",
    "ListActiveEventsQuery",
    "ListOrganizerEventsHandler",
    "ListOrganizerEventsQuery",
    "ListSpeakerSubmissionsHandler",
    "ListSpeakerSubmissionsQuery",
    "RegisterAttendeeCommand",
    "RegisterAttendeeHandler",
    "SubmitTalkCommand",
    "SubmitTalkHandler",
    "create_event_handler",
    "list_active_events_handler",
    "list_organizer_events_handler",
    "list_speaker_submissions_handler",
    "register_attendee_handler",
    "submit_talk_handler",
    "event_store",
    "ai_assessment_agent",
]
