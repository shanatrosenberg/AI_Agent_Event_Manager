from cqrs.commands import (
    ApproveTalkCommand,
    ApproveTalkHandler,
    CreateEventCommand,
    CreateEventHandler,
    DeleteEventCommand,
    DeleteEventHandler,
    DeleteRejectedTalkCommand,
    DeleteRejectedTalkHandler,
    LoginCommand,
    LoginHandler,
    RegisterAccountCommand,
    RegisterAccountHandler,
    RegisterAttendeeCommand,
    RegisterAttendeeHandler,
    RejectTalkCommand,
    RejectTalkHandler,
    RequestTalkCommand,
    RequestTalkHandler,
    RespondToTalkRequestCommand,
    RespondToTalkRequestHandler,
    RestoreTalkCommand,
    RestoreTalkHandler,
    SubmitTalkCommand,
    SubmitTalkHandler,
    UpdateEventCommand,
    UpdateEventHandler,
)
from cqrs.queries import (
    ListActiveEventsHandler,
    ListActiveEventsQuery,
    ListOrganizerEventsHandler,
    ListOrganizerEventsQuery,
    ListOrganizerRequestsHandler,
    ListOrganizerRequestsQuery,
    ListOrganizerSubmissionsHandler,
    ListOrganizerSubmissionsQuery,
    ListPendingProposalsHandler,
    ListPendingProposalsQuery,
    ListSpeakerRequestsHandler,
    ListSpeakerRequestsQuery,
    ListSpeakerSubmissionsHandler,
    ListSpeakerSubmissionsQuery,
    ListApprovedEventsHandler,
    ListApprovedEventsQuery,
    ListSpeakersHandler,
    ListSpeakersQuery,
    ListTrashHandler,
    ListTrashQuery,
)
from cqrs.store import EventStore
from services.ai_assessment import AIAssessmentAgent

event_store = EventStore()
ai_assessment_agent = AIAssessmentAgent()
create_event_handler = CreateEventHandler(event_store)
update_event_handler = UpdateEventHandler(event_store)
list_approved_events_handler = ListApprovedEventsHandler(event_store)
list_organizer_events_handler = ListOrganizerEventsHandler(event_store)
list_speakers_handler = ListSpeakersHandler(event_store)
submit_talk_handler = SubmitTalkHandler(event_store, ai_assessment_agent)
list_speaker_submissions_handler = ListSpeakerSubmissionsHandler(event_store)
list_speaker_requests_handler = ListSpeakerRequestsHandler(event_store)
list_organizer_requests_handler = ListOrganizerRequestsHandler(event_store)
list_organizer_submissions_handler = ListOrganizerSubmissionsHandler(event_store)
request_talk_handler = RequestTalkHandler(event_store)
respond_to_talk_request_handler = RespondToTalkRequestHandler(
    event_store, submit_talk_handler, create_event_handler
)
approve_talk_handler = ApproveTalkHandler(event_store, create_event_handler)
reject_talk_handler = RejectTalkHandler(event_store)
restore_talk_handler = RestoreTalkHandler(event_store)
delete_rejected_talk_handler = DeleteRejectedTalkHandler(event_store)
delete_event_handler = DeleteEventHandler(event_store)
list_pending_proposals_handler = ListPendingProposalsHandler(event_store)
list_trash_handler = ListTrashHandler(event_store)
list_active_events_handler = ListActiveEventsHandler(event_store)
register_attendee_handler = RegisterAttendeeHandler(event_store)
register_account_handler = RegisterAccountHandler(event_store)
login_handler = LoginHandler(event_store)

__all__ = [
    "ApproveTalkCommand",
    "ApproveTalkHandler",
    "CreateEventCommand",
    "CreateEventHandler",
    "LoginCommand",
    "LoginHandler",
    "RegisterAccountCommand",
    "RegisterAccountHandler",
    "ListActiveEventsHandler",
    "ListActiveEventsQuery",
    "ListOrganizerEventsHandler",
    "ListOrganizerEventsQuery",
    "ListOrganizerRequestsHandler",
    "ListOrganizerRequestsQuery",
    "ListOrganizerSubmissionsHandler",
    "ListOrganizerSubmissionsQuery",
    "ListSpeakerRequestsHandler",
    "ListSpeakerRequestsQuery",
    "ListSpeakerSubmissionsHandler",
    "ListSpeakerSubmissionsQuery",
    "ListSpeakersHandler",
    "ListSpeakersQuery",
    "RegisterAttendeeCommand",
    "RegisterAttendeeHandler",
    "RequestTalkCommand",
    "RequestTalkHandler",
    "RespondToTalkRequestCommand",
    "RespondToTalkRequestHandler",
    "SubmitTalkCommand",
    "SubmitTalkHandler",
    "UpdateEventCommand",
    "UpdateEventHandler",
    "ListApprovedEventsHandler",
    "ListApprovedEventsQuery",
    "DeleteEventCommand",
    "DeleteEventHandler",
    "DeleteRejectedTalkCommand",
    "DeleteRejectedTalkHandler",
    "ListPendingProposalsHandler",
    "ListPendingProposalsQuery",
    "ListTrashHandler",
    "ListTrashQuery",
    "RejectTalkCommand",
    "RejectTalkHandler",
    "RestoreTalkCommand",
    "RestoreTalkHandler",
    "approve_talk_handler",
    "create_event_handler",
    "delete_event_handler",
    "delete_rejected_talk_handler",
    "update_event_handler",
    "list_approved_events_handler",
    "login_handler",
    "register_account_handler",
    "list_active_events_handler",
    "list_organizer_events_handler",
    "list_organizer_requests_handler",
    "list_organizer_submissions_handler",
    "list_pending_proposals_handler",
    "list_speakers_handler",
    "list_speaker_requests_handler",
    "list_speaker_submissions_handler",
    "list_trash_handler",
    "register_attendee_handler",
    "reject_talk_handler",
    "request_talk_handler",
    "respond_to_talk_request_handler",
    "restore_talk_handler",
    "submit_talk_handler",
    "event_store",
    "ai_assessment_agent",
]
