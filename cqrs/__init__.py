from cqrs.commands import (
    AssessPendingTalksCommand,
    AssessPendingTalksHandler,
    ApproveTalkCommand,
    ApproveTalkHandler,
    ConfirmTalkCommand,
    ConfirmTalkHandler,
    CreateEventCommand,
    CreateEventHandler,
    DeleteEventCommand,
    DeleteEventHandler,
    DeleteRejectedTalkCommand,
    DeleteRejectedTalkHandler,
    DisapproveEventCommand,
    DisapproveEventHandler,
    PublishTalkCommand,
    PublishTalkHandler,
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
    ListEventLogHandler,
    ListEventLogQuery,
    ListOrganizerEventsHandler,
    ListOrganizerEventsQuery,
    ListOrganizerRequestsHandler,
    ListOrganizerRequestsQuery,
    ListOrganizerSubmissionsHandler,
    ListOrganizerSubmissionsQuery,
    ListPendingProposalsHandler,
    ListPendingProposalsQuery,
    ListSpeakerEventsHandler,
    ListSpeakerEventsQuery,
    ListSpeakerRequestsHandler,
    ListSpeakerRequestsQuery,
    ListSpeakerSubmissionsHandler,
    ListSpeakerSubmissionsQuery,
    ListApprovedEventsHandler,
    ListApprovedEventsQuery,
    ListAttendeeTicketsHandler,
    ListAttendeeTicketsQuery,
    ListSpeakersHandler,
    ListSpeakersQuery,
    ListTrashHandler,
    ListTrashQuery,
    OrganizerStatsHandler,
    OrganizerStatsQuery,
    ProjectTalksHandler,
    ProjectTalksQuery,
    SemanticSearchHandler,
    SemanticSearchQuery,
)
from cqrs.store import EventStore
from services.ai_assessment import AIAssessmentAgent

event_store = EventStore()
ai_assessment_agent = AIAssessmentAgent()
create_event_handler = CreateEventHandler(event_store)
update_event_handler = UpdateEventHandler(event_store)
list_approved_events_handler = ListApprovedEventsHandler(event_store)
list_attendee_tickets_handler = ListAttendeeTicketsHandler(event_store)
list_organizer_events_handler = ListOrganizerEventsHandler(event_store)
list_speakers_handler = ListSpeakersHandler(event_store)
submit_talk_handler = SubmitTalkHandler(event_store, ai_assessment_agent)
assess_pending_talks_handler = AssessPendingTalksHandler(event_store, ai_assessment_agent)
list_speaker_submissions_handler = ListSpeakerSubmissionsHandler(event_store)
list_speaker_events_handler = ListSpeakerEventsHandler(event_store)
list_speaker_requests_handler = ListSpeakerRequestsHandler(event_store)
list_organizer_requests_handler = ListOrganizerRequestsHandler(event_store)
list_organizer_submissions_handler = ListOrganizerSubmissionsHandler(event_store)
request_talk_handler = RequestTalkHandler(event_store)
respond_to_talk_request_handler = RespondToTalkRequestHandler(
    event_store, submit_talk_handler, create_event_handler
)
approve_talk_handler = ApproveTalkHandler(event_store, create_event_handler)
publish_talk_handler = PublishTalkHandler(event_store, create_event_handler)
confirm_talk_handler = ConfirmTalkHandler(event_store, create_event_handler)
reject_talk_handler = RejectTalkHandler(event_store)
disapprove_event_handler = DisapproveEventHandler(event_store, reject_talk_handler)
restore_talk_handler = RestoreTalkHandler(event_store)
delete_rejected_talk_handler = DeleteRejectedTalkHandler(event_store)
delete_event_handler = DeleteEventHandler(event_store)
list_pending_proposals_handler = ListPendingProposalsHandler(event_store)
list_trash_handler = ListTrashHandler(event_store)
organizer_stats_handler = OrganizerStatsHandler(event_store)
list_event_log_handler = ListEventLogHandler(event_store)
project_talks_handler = ProjectTalksHandler(event_store)
list_active_events_handler = ListActiveEventsHandler(event_store)
register_attendee_handler = RegisterAttendeeHandler(event_store)
register_account_handler = RegisterAccountHandler(event_store)
login_handler = LoginHandler(event_store)
semantic_search_handler = SemanticSearchHandler()

__all__ = [
    "AssessPendingTalksCommand",
    "AssessPendingTalksHandler",
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
    "ListSpeakerEventsHandler",
    "ListSpeakerEventsQuery",
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
    "ListAttendeeTicketsHandler",
    "ListAttendeeTicketsQuery",
    "DeleteEventCommand",
    "DeleteEventHandler",
    "DeleteRejectedTalkCommand",
    "DeleteRejectedTalkHandler",
    "DisapproveEventCommand",
    "DisapproveEventHandler",
    "ListPendingProposalsHandler",
    "ListPendingProposalsQuery",
    "ListEventLogHandler",
    "ListEventLogQuery",
    "ListTrashHandler",
    "ListTrashQuery",
    "OrganizerStatsHandler",
    "OrganizerStatsQuery",
    "ProjectTalksHandler",
    "ProjectTalksQuery",
    "SemanticSearchHandler",
    "SemanticSearchQuery",
    "RejectTalkCommand",
    "RejectTalkHandler",
    "RestoreTalkCommand",
    "RestoreTalkHandler",
    "ConfirmTalkCommand",
    "ConfirmTalkHandler",
    "PublishTalkCommand",
    "PublishTalkHandler",
    "approve_talk_handler",
    "confirm_talk_handler",
    "publish_talk_handler",
    "create_event_handler",
    "delete_event_handler",
    "delete_rejected_talk_handler",
    "disapprove_event_handler",
    "update_event_handler",
    "list_approved_events_handler",
    "list_attendee_tickets_handler",
    "login_handler",
    "register_account_handler",
    "list_active_events_handler",
    "list_organizer_events_handler",
    "list_organizer_requests_handler",
    "list_organizer_submissions_handler",
    "list_pending_proposals_handler",
    "list_speakers_handler",
    "list_speaker_events_handler",
    "list_speaker_requests_handler",
    "list_speaker_submissions_handler",
    "list_trash_handler",
    "organizer_stats_handler",
    "list_event_log_handler",
    "project_talks_handler",
    "register_attendee_handler",
    "reject_talk_handler",
    "request_talk_handler",
    "respond_to_talk_request_handler",
    "restore_talk_handler",
    "submit_talk_handler",
    "assess_pending_talks_handler",
    "semantic_search_handler",
    "event_store",
    "ai_assessment_agent",
]
