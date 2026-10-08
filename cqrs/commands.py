from dataclasses import dataclass
from uuid import uuid4

from models.booking import Booking
from models.event import Event
from models.submission import (
    DEFAULT_REJECTION_MESSAGE,
    TalkSubmission,
    utc_now,
)
from models.talk_request import TalkRequest
from cqrs.errors import DomainError
from cqrs.store import EventStore
from services.ai_assessment import AIAssessmentAgent
from services.auth import (
    INVALID_CREDENTIALS,
    VALID_ROLES,
    admin_organizer_id,
    is_admin_alias,
    verify_password,
)


@dataclass
class CreateEventCommand:
    organizer_id: str
    title: str
    description: str
    date: str
    start_time: str
    end_time: str
    capacity: int
    speaker_id: str | None = None


class CreateEventHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: CreateEventCommand) -> Event:
        from services.scheduling import normalize_schedule

        self._store.ensure_organizer(command.organizer_id)
        speaker_id = (command.speaker_id or "").strip() or None
        if speaker_id and self._store.get_speaker(speaker_id) is None:
            raise DomainError("speaker not found", status=404)
        try:
            date, start_time, end_time, capacity = normalize_schedule(
                command.date, command.start_time, command.end_time, command.capacity
            )
        except ValueError as exc:
            raise DomainError(str(exc)) from exc
        conflict = self._store.find_hall_conflict(capacity, date, start_time, end_time)
        if conflict is not None:
            raise DomainError(
                "This hall is already booked for an overlapping date and time.",
                status=409,
            )
        event = Event(
            id=str(uuid4()),
            organizer_id=command.organizer_id,
            speaker_id=speaker_id,
            title=command.title,
            description=command.description,
            date=date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            seats_booked=0,
            status="approved",
        )
        self._store.append("EventCreated", event.to_dict())
        self._store.save_read_model(event)
        try:
            from services.vector_store import index_official_event

            index_official_event(event)
        except Exception:
            pass
        return event


@dataclass
class UpdateEventCommand:
    organizer_id: str
    event_id: str
    title: str
    description: str
    date: str
    start_time: str
    end_time: str
    capacity: int
    speaker_id: str | None = None


class UpdateEventHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: UpdateEventCommand) -> Event:
        from services.scheduling import normalize_schedule

        event = self._store.get_event(command.event_id)
        if event is None:
            raise DomainError("event not found", status=404)
        if event.organizer_id != command.organizer_id:
            raise DomainError("event does not belong to this organizer", status=403)
        speaker_id = (command.speaker_id or "").strip() or None
        if speaker_id and self._store.get_speaker(speaker_id) is None:
            raise DomainError("speaker not found", status=404)
        try:
            date, start_time, end_time, capacity = normalize_schedule(
                command.date, command.start_time, command.end_time, command.capacity
            )
        except ValueError as exc:
            raise DomainError(str(exc)) from exc
        conflict = self._store.find_hall_conflict(
            capacity, date, start_time, end_time, exclude_event_id=event.id
        )
        if conflict is not None:
            raise DomainError(
                "This hall is already booked for an overlapping date and time.",
                status=409,
            )
        event.title = command.title
        event.description = command.description
        event.date = date
        event.start_time = start_time
        event.end_time = end_time
        event.capacity = capacity
        event.speaker_id = speaker_id
        event.status = "approved"
        self._store.append("EventUpdated", event.to_dict())
        self._store.save_read_model(event)
        try:
            from services.vector_store import index_official_event

            index_official_event(event)
        except Exception:
            pass
        return event


@dataclass
class SubmitTalkCommand:
    speaker_id: str
    title: str
    abstract: str
    category: str
    organizer_id: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    capacity: int | None = None


class SubmitTalkHandler:
    def __init__(self, store: EventStore, assessor: AIAssessmentAgent | None = None) -> None:
        self._store = store
        self._assessor = assessor or AIAssessmentAgent()

    def handle(self, command: SubmitTalkCommand) -> TalkSubmission:
        from services.scheduling import normalize_schedule

        self._store.ensure_speaker(command.speaker_id)
        organizer_id = (command.organizer_id or "").strip() or admin_organizer_id()
        self._store.ensure_organizer(organizer_id)
        date = start_time = end_time = None
        capacity = None
        has_schedule = any(
            [
                command.date,
                command.start_time,
                command.end_time,
                command.capacity is not None,
            ]
        )
        if has_schedule:
            try:
                date, start_time, end_time, capacity = normalize_schedule(
                    command.date or "",
                    command.start_time or "",
                    command.end_time or "",
                    int(command.capacity) if command.capacity is not None else 0,
                )
            except (TypeError, ValueError) as exc:
                raise DomainError(str(exc) if str(exc) else "Hall capacity must be 50, 100, or 300 seats.") from exc
        submission = TalkSubmission(
            id=str(uuid4()),
            speaker_id=command.speaker_id,
            organizer_id=organizer_id,
            title=command.title,
            abstract=command.abstract,
            category=command.category,
            date=date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            status="pending_assessment",
            ai_assessment={},
        )
        self._store.append("TalkProposed", submission.to_dict())

        assessment = self._assessor.enqueue(submission)
        submission.ai_assessment = assessment
        submission.status = "under_review"
        self._store.append("TalkQueuedForAssessment", submission.to_dict())
        self._store.append("TalkInnovationReviewed", submission.to_dict())
        self._store.save_submission(submission)
        try:
            from services.vector_store import index_talk_proposal

            index_talk_proposal(submission)
        except Exception:
            pass
        return submission


@dataclass
class AssessPendingTalksCommand:
    submission_id: str | None = None
    force: bool = False


class AssessPendingTalksHandler:
    def __init__(self, store: EventStore, assessor: AIAssessmentAgent | None = None) -> None:
        self._store = store
        self._assessor = assessor or AIAssessmentAgent()

    def handle(self, command: AssessPendingTalksCommand) -> list[dict]:
        from services.deep_agent import assess_pending_talks

        return assess_pending_talks(
            submission_id=command.submission_id,
            force=command.force,
            assessor=self._assessor,
            store=self._store,
        )


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

        from services.scheduling import BOOKABLE_STATUSES

        if event.status not in BOOKABLE_STATUSES:
            raise DomainError("event is not active", status=409)

        if self._store.has_booking(command.attendee_id, command.event_id):
            raise DomainError("attendee is already registered for this event", status=409)

        if command.seats > event.remaining_seats:
            raise DomainError(
                f"not enough seats remaining ({event.remaining_seats} available)",
                status=409,
            )

        self._store.ensure_attendee(command.attendee_id)
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


@dataclass
class RegisterAccountCommand:
    user_id: str
    password: str
    role: str
    name: str | None = None


class RegisterAccountHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: RegisterAccountCommand) -> dict:
        role = (command.role or "").strip().lower()
        user_id = (command.user_id or "").strip()
        password = command.password or ""
        name = (command.name or "").strip() or user_id

        if role == "organizer":
            raise DomainError("organizer accounts cannot be self-registered", status=403)
        if role not in VALID_ROLES:
            raise DomainError("role must be organizer, speaker, or attendee")
        if not user_id:
            raise DomainError("user id is required")
        if len(user_id) > 64:
            raise DomainError("user id must be 64 characters or fewer")
        if len(password) < 8:
            raise DomainError("password must be at least 8 characters")

        account = self._store.get_account(role, user_id)
        if account is not None and account.password_hash:
            raise DomainError("an account with this id already exists", status=409)

        if account is None:
            account = self._store.create_account(role, user_id, name)
        elif not account.name:
            account.name = name

        account.set_password(password)
        self._store.append(
            "AccountRegistered",
            {"user_id": account.id, "role": role, "name": account.name},
        )
        self._store.save_account(account)
        return {"user_id": account.id, "role": role, "name": account.name}


@dataclass
class LoginCommand:
    user_id: str
    password: str
    role: str


class LoginHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: LoginCommand) -> dict:
        role = (command.role or "").strip().lower()
        user_id = (command.user_id or "").strip()
        password = command.password or ""

        if role not in VALID_ROLES or not user_id or not password:
            raise DomainError(INVALID_CREDENTIALS, status=401)

        if role == "organizer":
            if not is_admin_alias(user_id):
                verify_password(None, password)
                raise DomainError(INVALID_CREDENTIALS, status=401)
            user_id = admin_organizer_id()

        account = self._store.find_account(role, user_id)
        if account is None or not account.password_hash:
            verify_password(None, password)
            raise DomainError(INVALID_CREDENTIALS, status=401)
        if not verify_password(account, password):
            raise DomainError(INVALID_CREDENTIALS, status=401)

        session_state = {
            "user_id": account.id,
            "role": role,
            "name": account.name or account.id,
        }
        self._store.append(
            "UserLoggedIn",
            {"user_id": account.id, "role": role},
        )
        self._store.save_account(account)
        return session_state


@dataclass
class RequestTalkCommand:
    organizer_id: str
    speaker_id: str
    topic: str
    details: str = ""
    category: str = "invitation"
    date: str = ""
    start_time: str = ""
    end_time: str = ""
    capacity: int | None = None


class RequestTalkHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: RequestTalkCommand) -> TalkRequest:
        from services.scheduling import normalize_schedule

        speaker_id = (command.speaker_id or "").strip()
        topic = (command.topic or "").strip()
        if not speaker_id or not topic:
            raise DomainError("speaker and topic are required")
        if self._store.get_speaker(speaker_id) is None:
            raise DomainError("speaker not found", status=404)

        organizer_id = (command.organizer_id or "").strip() or admin_organizer_id()
        self._store.ensure_organizer(organizer_id)
        try:
            date, start_time, end_time, capacity = normalize_schedule(
                command.date,
                command.start_time,
                command.end_time,
                int(command.capacity) if command.capacity is not None else 0,
            )
        except (TypeError, ValueError) as exc:
            raise DomainError(str(exc) if str(exc) else "Hall capacity must be 50, 100, or 300 seats.") from exc
        conflict = self._store.find_hall_conflict(capacity, date, start_time, end_time)
        if conflict is not None:
            raise DomainError(
                "This hall is already booked for an overlapping date and time.",
                status=409,
            )
        talk_request = TalkRequest(
            id=str(uuid4()),
            organizer_id=organizer_id,
            speaker_id=speaker_id,
            topic=topic,
            details=(command.details or "").strip(),
            category=(command.category or "invitation").strip() or "invitation",
            date=date,
            start_time=start_time,
            end_time=end_time,
            capacity=capacity,
            status="pending",
        )
        self._store.append("TalkRequested", talk_request.to_dict())
        self._store.save_talk_request(talk_request)
        return talk_request


@dataclass
class RespondToTalkRequestCommand:
    speaker_id: str
    request_id: str
    accept: bool


class RespondToTalkRequestHandler:
    def __init__(
        self,
        store: EventStore,
        submit_handler: SubmitTalkHandler,
        create_event_handler: CreateEventHandler,
    ) -> None:
        self._store = store
        self._submit_handler = submit_handler
        self._create_event_handler = create_event_handler

    def handle(self, command: RespondToTalkRequestCommand) -> TalkRequest:
        talk_request = self._store.get_talk_request(command.request_id)
        if talk_request is None:
            raise DomainError("talk request not found", status=404)
        if talk_request.speaker_id != command.speaker_id:
            raise DomainError("talk request does not belong to this speaker", status=403)
        if talk_request.status != "pending":
            raise DomainError("talk request has already been answered", status=409)

        if command.accept:
            submission = self._submit_handler.handle(
                SubmitTalkCommand(
                    speaker_id=command.speaker_id,
                    title=talk_request.topic,
                    abstract=talk_request.details or f"Invited to present: {talk_request.topic}",
                    category=talk_request.category,
                    organizer_id=talk_request.organizer_id,
                    date=talk_request.date,
                    start_time=talk_request.start_time,
                    end_time=talk_request.end_time,
                    capacity=talk_request.capacity,
                )
            )
            event = self._create_event_handler.handle(
                CreateEventCommand(
                    organizer_id=talk_request.organizer_id,
                    title=talk_request.topic,
                    description=talk_request.details or talk_request.topic,
                    date=talk_request.date or "",
                    start_time=talk_request.start_time or "",
                    end_time=talk_request.end_time or "",
                    capacity=talk_request.capacity or 0,
                    speaker_id=command.speaker_id,
                )
            )
            submission.status = "approved"
            submission.event_id = event.id
            self._store.append("TalkApproved", submission.to_dict())
            self._store.save_submission(submission)
            talk_request.status = "accepted"
            talk_request.submission_id = submission.id
            talk_request.event_id = event.id
            self._store.append("TalkRequestAccepted", talk_request.to_dict())
        else:
            talk_request.status = "declined"
            self._store.append("TalkRequestDeclined", talk_request.to_dict())

        self._store.save_talk_request(talk_request)
        return talk_request


@dataclass
class ApproveTalkCommand:
    organizer_id: str
    submission_id: str


def publish_submission_as_event(
    store: EventStore,
    create_event_handler: CreateEventHandler,
    submission: TalkSubmission,
    organizer_id: str,
) -> TalkSubmission:
    if submission.status == "approved" and submission.event_id:
        return submission
    if submission.status == "rejected":
        raise DomainError("Restore this proposal from trash before publishing it.", status=409)
    if not submission.date or not submission.start_time or not submission.end_time or not submission.capacity:
        raise DomainError("proposal is missing a date, time, or hall")
    event = create_event_handler.handle(
        CreateEventCommand(
            organizer_id=organizer_id,
            title=submission.title,
            description=submission.abstract,
            date=submission.date,
            start_time=submission.start_time,
            end_time=submission.end_time,
            capacity=int(submission.capacity),
            speaker_id=submission.speaker_id,
        )
    )
    submission.status = "approved"
    submission.event_id = event.id
    submission.rejected_at = None
    submission.rejection_message = None
    store.append("TalkPublished", submission.to_dict())
    store.save_submission(submission)
    return submission


class ApproveTalkHandler:
    def __init__(self, store: EventStore, create_event_handler: CreateEventHandler | None = None) -> None:
        self._store = store
        self._create_event_handler = create_event_handler or CreateEventHandler(store)

    def handle(self, command: ApproveTalkCommand) -> TalkSubmission:
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        organizer_id = command.organizer_id or admin_organizer_id()
        if submission.organizer_id and submission.organizer_id != organizer_id:
            raise DomainError("submission does not belong to this organizer", status=403)
        if submission.status == "rejected":
            raise DomainError("Restore this proposal from trash before approving it.", status=409)
        published = publish_submission_as_event(
            self._store, self._create_event_handler, submission, organizer_id
        )
        self._store.append("TalkApproved", published.to_dict())
        return published


@dataclass
class PublishTalkCommand:
    organizer_id: str
    submission_id: str


class PublishTalkHandler:
    def __init__(self, store: EventStore, create_event_handler: CreateEventHandler | None = None) -> None:
        self._store = store
        self._create_event_handler = create_event_handler or CreateEventHandler(store)

    def handle(self, command: PublishTalkCommand) -> TalkSubmission:
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        organizer_id = command.organizer_id or admin_organizer_id()
        if submission.organizer_id and submission.organizer_id != organizer_id:
            raise DomainError("submission does not belong to this organizer", status=403)
        return publish_submission_as_event(
            self._store, self._create_event_handler, submission, organizer_id
        )


@dataclass
class ConfirmTalkCommand:
    speaker_id: str
    submission_id: str
    confirm: bool = True


class ConfirmTalkHandler:
    def __init__(self, store: EventStore, create_event_handler: CreateEventHandler | None = None) -> None:
        self._store = store
        self._create_event_handler = create_event_handler or CreateEventHandler(store)

    def handle(self, command: ConfirmTalkCommand) -> TalkSubmission:
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        if submission.speaker_id != command.speaker_id:
            raise DomainError("submission does not belong to this speaker", status=403)
        if submission.status != "awaiting_speaker_confirmation":
            raise DomainError("this talk is not waiting for speaker confirmation", status=409)
        organizer_id = submission.organizer_id or admin_organizer_id()
        if command.confirm:
            published = publish_submission_as_event(
                self._store, self._create_event_handler, submission, organizer_id
            )
            self._store.append("TalkConfirmedBySpeaker", published.to_dict())
            return published
        submission.status = "confirmation_declined"
        submission.rejection_message = "The speaker cannot deliver this talk at the requested time."
        self._store.append("TalkConfirmationDeclined", submission.to_dict())
        self._store.save_submission(submission)
        return submission


@dataclass
class RejectTalkCommand:
    organizer_id: str
    submission_id: str
    message: str | None = None


class RejectTalkHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: RejectTalkCommand) -> TalkSubmission:
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        organizer_id = command.organizer_id or admin_organizer_id()
        if submission.organizer_id and submission.organizer_id != organizer_id:
            raise DomainError("submission does not belong to this organizer", status=403)
        if submission.event_id:
            event = self._store.get_event(submission.event_id)
            if event is not None:
                event.status = "disapproved"
                self._store.append("EventDisapproved", event.to_dict())
                self._store.save_read_model(event)
        note = (command.message or DEFAULT_REJECTION_MESSAGE).strip() or DEFAULT_REJECTION_MESSAGE
        submission.status = "rejected"
        submission.rejected_at = utc_now()
        submission.rejection_message = note
        payload = submission.to_dict()
        self._store.append("TalkRejected", payload)
        self._store.append(
            "SpeakerNotified",
            {
                "speaker_id": submission.speaker_id,
                "submission_id": submission.id,
                "title": submission.title,
                "kind": "proposal_rejected",
                "message": note,
            },
        )
        self._store.save_submission(submission)
        return submission


@dataclass
class DisapproveEventCommand:
    organizer_id: str
    event_id: str
    message: str | None = None


class DisapproveEventHandler:
    def __init__(self, store: EventStore, reject_handler: RejectTalkHandler) -> None:
        self._store = store
        self._reject_handler = reject_handler

    def handle(self, command: DisapproveEventCommand) -> TalkSubmission:
        event = self._store.get_event(command.event_id)
        if event is None:
            raise DomainError("event not found", status=404)
        organizer_id = command.organizer_id or admin_organizer_id()
        if event.organizer_id != organizer_id:
            raise DomainError("event does not belong to this organizer", status=403)
        submission = self._store.get_submission_by_event_id(event.id)
        if submission is None:
            speaker_id = (event.speaker_id or "").strip() or "unassigned"
            self._store.ensure_speaker(speaker_id)
            submission = TalkSubmission(
                id=str(uuid4()),
                speaker_id=speaker_id,
                organizer_id=organizer_id,
                title=event.title,
                abstract=event.description or event.title,
                category="event",
                date=event.date,
                start_time=event.start_time,
                end_time=event.end_time,
                capacity=event.capacity,
                status="approved",
                ai_assessment={},
                event_id=event.id,
            )
            self._store.save_submission(submission)
        return self._reject_handler.handle(
            RejectTalkCommand(
                organizer_id=organizer_id,
                submission_id=submission.id,
                message=command.message,
            )
        )


@dataclass
class RestoreTalkCommand:
    submission_id: str
    organizer_id: str | None = None
    speaker_id: str | None = None


class RestoreTalkHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: RestoreTalkCommand) -> TalkSubmission:
        self._store.purge_expired_rejections()
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        if command.speaker_id:
            if submission.speaker_id != command.speaker_id:
                raise DomainError("submission does not belong to this speaker", status=403)
            raise DomainError("Rejected proposals are removed from the speaker dashboard.", status=403)
        else:
            organizer_id = command.organizer_id or admin_organizer_id()
            if submission.organizer_id and submission.organizer_id != organizer_id:
                raise DomainError("submission does not belong to this organizer", status=403)
        if submission.status != "rejected":
            raise DomainError("only rejected proposals can be restored", status=409)
        if submission.is_expired:
            raise DomainError("this proposal has expired from trash", status=410)
        if submission.event_id:
            event = self._store.get_event(submission.event_id)
            if event is not None:
                if event.start_time and event.end_time and event.capacity:
                    conflict = self._store.find_hall_conflict(
                        event.capacity,
                        event.date,
                        event.start_time,
                        event.end_time,
                        exclude_event_id=event.id,
                    )
                    if conflict is not None:
                        raise DomainError(
                            "This hall is already booked for an overlapping date and time.",
                            status=409,
                        )
                event.status = "approved"
                self._store.append("EventRestored", event.to_dict())
                self._store.save_read_model(event)
            submission.status = "approved"
        else:
            submission.status = "under_review"
        submission.rejected_at = None
        submission.rejection_message = None
        self._store.append("TalkRestored", submission.to_dict())
        self._store.save_submission(submission)
        return submission


@dataclass
class DeleteRejectedTalkCommand:
    organizer_id: str
    submission_id: str


class DeleteRejectedTalkHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: DeleteRejectedTalkCommand) -> dict:
        submission = self._store.get_submission(command.submission_id)
        if submission is None:
            raise DomainError("submission not found", status=404)
        organizer_id = command.organizer_id or admin_organizer_id()
        if submission.organizer_id and submission.organizer_id != organizer_id:
            raise DomainError("submission does not belong to this organizer", status=403)
        if submission.status != "rejected":
            raise DomainError("only rejected proposals can be deleted from trash", status=409)
        payload = {"id": submission.id, "title": submission.title, "event_id": submission.event_id}
        if submission.event_id:
            event = self._store.get_event(submission.event_id)
            if event is not None:
                self._store.append("EventDeleted", {"id": event.id, "title": event.title})
                self._store.delete_event(event)
        self._store.append("TalkDeleted", payload)
        self._store.delete_submission(submission)
        try:
            from services.vector_store import remove_document

            remove_document("proposal", payload["id"])
        except Exception:
            pass
        return payload


@dataclass
class DeleteEventCommand:
    organizer_id: str
    event_id: str


class DeleteEventHandler:
    def __init__(self, store: EventStore) -> None:
        self._store = store

    def handle(self, command: DeleteEventCommand) -> dict:
        event = self._store.get_event(command.event_id)
        if event is None:
            raise DomainError("event not found", status=404)
        if event.organizer_id != command.organizer_id:
            raise DomainError("event does not belong to this organizer", status=403)
        payload = {"id": event.id, "title": event.title}
        self._store.append("EventDeleted", payload)
        self._store.delete_event(event)
        return payload
