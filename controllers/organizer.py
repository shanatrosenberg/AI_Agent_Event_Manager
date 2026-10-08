from flask import Blueprint, current_app, jsonify, request

from cqrs import (
    AssessPendingTalksCommand,
    ApproveTalkCommand,
    DeleteEventCommand,
    DeleteRejectedTalkCommand,
    DisapproveEventCommand,
    ListEventLogQuery,
    ListOrganizerEventsQuery,
    ListOrganizerRequestsQuery,
    ListOrganizerSubmissionsQuery,
    ListPendingProposalsQuery,
    ListSpeakersQuery,
    ListTrashQuery,
    OrganizerStatsQuery,
    ProjectTalksQuery,
    PublishTalkCommand,
    RejectTalkCommand,
    RequestTalkCommand,
    RestoreTalkCommand,
    UpdateEventCommand,
    assess_pending_talks_handler,
    approve_talk_handler,
    delete_event_handler,
    delete_rejected_talk_handler,
    disapprove_event_handler,
    list_event_log_handler,
    list_organizer_events_handler,
    list_organizer_requests_handler,
    list_organizer_submissions_handler,
    list_pending_proposals_handler,
    list_speakers_handler,
    list_trash_handler,
    organizer_stats_handler,
    project_talks_handler,
    publish_talk_handler,
    reject_talk_handler,
    request_talk_handler,
    restore_talk_handler,
    update_event_handler,
    event_store,
)
from cqrs.errors import DomainError
from extensions import db
from models.talk_request import AWAITING_STATUSES, CONFIRMED_STATUSES
from controllers.search import run_semantic_search
from services.auth import admin_organizer_id, current_user

organizer_bp = Blueprint("organizer", __name__, url_prefix="/api/organizer")

REQUIRED_CREATE_FIELDS = ("title", "description", "date", "start_time", "end_time", "capacity")


def _organizer_id() -> str | None:
    user = current_user()
    if user and user["role"] == "organizer":
        return admin_organizer_id()
    if current_app.config.get("TESTING"):
        return (
            request.headers.get("X-Organizer-Id")
            or request.args.get("organizer_id")
            or (request.get_json(silent=True) or {}).get("organizer_id")
        )
    return None


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _confirmation_filter(raw: str | None) -> str | None:
    value = str(raw or "").strip().lower()
    if value in {"", "all"}:
        return None
    if value in {"awaiting", "pending", "awaiting_speaker_confirmation"}:
        return "awaiting"
    if value in {"confirmed", "accepted", "approved", "speaker_confirmed"}:
        return "confirmed"
    return "invalid"


def _proposal_confirmation_item(submission) -> dict:
    item = submission.to_dict()
    confirmed = submission.status == "approved" and bool(submission.event_id)
    item["kind"] = "proposal"
    item["topic"] = submission.title
    item["confirmation"] = "confirmed" if confirmed else "awaiting"
    item["display_status"] = "Speaker Confirmed" if confirmed else submission.display_status
    return item


def _event_command_fields(payload: dict) -> dict:
    try:
        capacity = int(payload["capacity"])
    except (TypeError, ValueError) as exc:
        raise DomainError("capacity must be an integer") from exc

    title = str(payload["title"]).strip()
    description = str(payload["description"]).strip()
    date = str(payload["date"]).strip()
    start_time = str(payload.get("start_time") or payload.get("start") or "").strip()
    end_time = str(payload.get("end_time") or payload.get("end") or "").strip()
    if not title or not date:
        raise DomainError("title and date cannot be empty")
    speaker_id = str(payload.get("speaker_id") or payload.get("speaker") or "").strip() or None
    return {
        "title": title,
        "description": description,
        "date": date,
        "start_time": start_time,
        "end_time": end_time,
        "capacity": capacity,
        "speaker_id": speaker_id,
    }


@organizer_bp.route("/events/<event_id>", methods=["PUT", "PATCH"])
def update_event(event_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    missing = [field for field in REQUIRED_CREATE_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return _validation_error(f"Missing required fields: {', '.join(missing)}")

    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")

    try:
        event = update_event_handler.handle(
            UpdateEventCommand(
                organizer_id=str(organizer_id),
                event_id=str(event_id).strip(),
                **_event_command_fields(payload),
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(event.to_dict()), 200


@organizer_bp.route("/events", methods=["GET"])
def list_events():
    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")

    events = list_organizer_events_handler.handle(
        ListOrganizerEventsQuery(organizer_id=organizer_id)
    )
    return jsonify([event.to_dict() for event in events]), 200


@organizer_bp.route("/event-log", methods=["GET"])
def list_event_log():
    organizer_id = _organizer_id() or admin_organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")
    try:
        limit = int(request.args.get("limit") or 200)
    except (TypeError, ValueError):
        limit = 200
    events = list_event_log_handler.handle(
        ListEventLogQuery(
            limit=limit,
            event_name=request.args.get("event_name") or request.args.get("type"),
            aggregate_id=request.args.get("aggregate_id") or request.args.get("talk_id"),
        )
    )
    return jsonify(events), 200


@organizer_bp.route("/projections/talks", methods=["GET"])
def list_talk_projections():
    organizer_id = _organizer_id() or admin_organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")
    talks = project_talks_handler.handle(
        ProjectTalksQuery(submission_id=request.args.get("submission_id") or request.args.get("talk_id"))
    )
    return jsonify(talks), 200


@organizer_bp.route("/stats", methods=["GET"])
def organizer_stats():
    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")
    return jsonify(organizer_stats_handler.handle(OrganizerStatsQuery(organizer_id=organizer_id))), 200


@organizer_bp.route("/search", methods=["GET", "POST"])
def search_proposals():
    return run_semantic_search()


@organizer_bp.route("/speakers", methods=["GET"])
def list_speakers():
    speakers = list_speakers_handler.handle(ListSpeakersQuery())
    return jsonify([speaker.to_dict() for speaker in speakers]), 200


@organizer_bp.route("/requests", methods=["GET"])
def list_requests():
    organizer_id = _organizer_id() or admin_organizer_id()
    confirmation = _confirmation_filter(request.args.get("confirmation") or request.args.get("status"))
    if confirmation == "invalid":
        return _validation_error("confirmation must be awaiting or confirmed")

    request_statuses = None
    if confirmation == "awaiting":
        request_statuses = AWAITING_STATUSES
    elif confirmation == "confirmed":
        request_statuses = CONFIRMED_STATUSES

    invitations = list_organizer_requests_handler.handle(
        ListOrganizerRequestsQuery(organizer_id=organizer_id, statuses=request_statuses)
    )
    items = [item.to_dict() for item in invitations]
    if confirmation is None:
        return jsonify(items), 200

    submissions = list_organizer_submissions_handler.handle(
        ListOrganizerSubmissionsQuery(organizer_id=organizer_id)
    )
    linked_ids = {item.submission_id for item in invitations if item.submission_id}
    if confirmation == "awaiting":
        proposals = [
            _proposal_confirmation_item(item)
            for item in submissions
            if item.status == "awaiting_speaker_confirmation"
        ]
    else:
        proposals = [
            _proposal_confirmation_item(item)
            for item in submissions
            if item.status == "approved" and item.event_id and item.id not in linked_ids
        ]
    items.extend(proposals)
    items.sort(key=lambda item: (item.get("title") or item.get("topic") or "").lower())
    return jsonify(items), 200


@organizer_bp.route("/requests", methods=["POST"])
def create_request():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    organizer_id = _organizer_id() or admin_organizer_id()
    speaker_id = str(payload.get("speaker_id") or "").strip()
    topic = str(payload.get("topic") or payload.get("title") or "").strip()
    details = str(payload.get("details") or payload.get("message") or "").strip()
    category = str(payload.get("category") or "invitation").strip() or "invitation"
    date = str(payload.get("date") or "").strip()
    start_time = str(payload.get("start_time") or payload.get("start") or "").strip()
    end_time = str(payload.get("end_time") or payload.get("end") or "").strip()
    if not speaker_id or not topic:
        return _validation_error("speaker_id and topic are required")
    if not date or not start_time or not end_time or payload.get("capacity") in (None, ""):
        return _validation_error("date, start_time, end_time, and capacity are required")
    try:
        capacity = int(payload["capacity"])
    except (TypeError, ValueError):
        return _validation_error("capacity must be an integer")

    try:
        talk_request = request_talk_handler.handle(
            RequestTalkCommand(
                organizer_id=organizer_id,
                speaker_id=speaker_id,
                topic=topic,
                details=details,
                category=category,
                date=date,
                start_time=start_time,
                end_time=end_time,
                capacity=capacity,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(talk_request.to_dict()), 201


@organizer_bp.route("/submissions", methods=["GET"])
def list_submissions():
    organizer_id = _organizer_id() or admin_organizer_id()
    submissions = list_organizer_submissions_handler.handle(
        ListOrganizerSubmissionsQuery(organizer_id=organizer_id)
    )
    return jsonify([item.to_dict() for item in submissions]), 200


@organizer_bp.route("/proposals", methods=["GET"])
def list_proposals():
    organizer_id = _organizer_id() or admin_organizer_id()
    submissions = list_pending_proposals_handler.handle(
        ListPendingProposalsQuery(organizer_id=organizer_id)
    )
    return jsonify([item.to_dict() for item in submissions]), 200


@organizer_bp.route("/proposals/<submission_id>", methods=["GET"])
def get_proposal(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    submissions = list_organizer_submissions_handler.handle(
        ListOrganizerSubmissionsQuery(organizer_id=organizer_id)
    )
    match = next((item for item in submissions if item.id == str(submission_id).strip()), None)
    if match is None:
        return _validation_error("submission not found", status=404)
    return jsonify(match.to_dict()), 200


@organizer_bp.route("/proposals/<submission_id>/publish", methods=["POST"])
def publish_submission(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    try:
        submission = publish_talk_handler.handle(
            PublishTalkCommand(organizer_id=organizer_id, submission_id=str(submission_id).strip())
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200


@organizer_bp.route("/proposals/<submission_id>/assess", methods=["POST"])
def assess_proposal(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    submission = event_store.get_submission(str(submission_id).strip())
    if submission is None:
        return _validation_error("submission not found", status=404)
    owned = (
        submission.organizer_id in {None, "", organizer_id}
        or submission.organizer_id == admin_organizer_id()
    )
    if not owned:
        return _validation_error("submission not found", status=404)
    assessed = assess_pending_talks_handler.handle(
        AssessPendingTalksCommand(submission_id=str(submission_id).strip(), force=True)
    )
    if not assessed:
        return _validation_error("submission not found", status=404)
    refreshed = event_store.get_submission(str(submission_id).strip())
    return jsonify((refreshed or submission).to_dict()), 200


@organizer_bp.route("/proposals/<submission_id>/approve", methods=["POST"])
@organizer_bp.route("/submissions/<submission_id>/approve", methods=["POST"])
def approve_submission(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    try:
        submission = approve_talk_handler.handle(
            ApproveTalkCommand(organizer_id=organizer_id, submission_id=str(submission_id).strip())
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    payload = submission.to_dict()
    if submission.event_id:
        event = event_store.get_event(submission.event_id)
        if event is not None:
            payload["event"] = event.to_dict()
    return jsonify(payload), 200


@organizer_bp.route("/proposals/<submission_id>/reject", methods=["POST"])
def reject_submission(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") if isinstance(payload, dict) else None
    try:
        submission = reject_talk_handler.handle(
            RejectTalkCommand(
                organizer_id=organizer_id,
                submission_id=str(submission_id).strip(),
                message=str(message).strip() if message else None,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200


@organizer_bp.route("/trash", methods=["GET"])
def list_trash():
    organizer_id = _organizer_id() or admin_organizer_id()
    items = list_trash_handler.handle(ListTrashQuery(organizer_id=organizer_id))
    return jsonify([item.to_dict() for item in items]), 200


@organizer_bp.route("/trash/<submission_id>/restore", methods=["POST"])
def restore_trash(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    try:
        submission = restore_talk_handler.handle(
            RestoreTalkCommand(organizer_id=organizer_id, submission_id=str(submission_id).strip())
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200


@organizer_bp.route("/trash/<submission_id>", methods=["DELETE"])
def delete_trash(submission_id: str):
    organizer_id = _organizer_id() or admin_organizer_id()
    try:
        payload = delete_rejected_talk_handler.handle(
            DeleteRejectedTalkCommand(organizer_id=organizer_id, submission_id=str(submission_id).strip())
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(payload), 200


@organizer_bp.route("/events/<event_id>/reject", methods=["POST"])
def reject_event(event_id: str):
    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")
    payload = request.get_json(silent=True) or {}
    message = payload.get("message") if isinstance(payload, dict) else None
    try:
        submission = disapprove_event_handler.handle(
            DisapproveEventCommand(
                organizer_id=str(organizer_id),
                event_id=str(event_id).strip(),
                message=str(message).strip() if message else None,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200


@organizer_bp.route("/events/<event_id>", methods=["DELETE"])
def delete_event(event_id: str):
    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (sign in as admin, or send X-Organizer-Id in tests)")
    try:
        payload = delete_event_handler.handle(
            DeleteEventCommand(organizer_id=str(organizer_id), event_id=str(event_id).strip())
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(payload), 200
