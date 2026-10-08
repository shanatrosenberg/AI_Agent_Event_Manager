from flask import Blueprint, current_app, jsonify, request, session
from cqrs import (
    ConfirmTalkCommand,
    ListSpeakerEventsQuery,
    ListSpeakerRequestsQuery,
    ListSpeakerSubmissionsQuery,
    RespondToTalkRequestCommand,
    RestoreTalkCommand,
    SubmitTalkCommand,
    confirm_talk_handler,
    event_store,
    list_speaker_events_handler,
    list_speaker_requests_handler,
    list_speaker_submissions_handler,
    respond_to_talk_request_handler,
    restore_talk_handler,
    submit_talk_handler,
)
from cqrs.errors import DomainError
from extensions import db
from services.abstract_enhancer import enhance_abstract
from services.auth import admin_organizer_id, current_user

speaker_bp = Blueprint("speaker", __name__, url_prefix="/api/speaker")

REQUIRED_SUBMIT_FIELDS = ("title", "abstract", "category", "date", "start_time", "end_time", "capacity")


def _authenticated_speaker() -> dict | None:
    user = current_user()
    if user and user.get("role") == "speaker":
        return user
    if session.get("role") == "speaker":
        user_id = (session.get("user_id") or session.get("speaker_id") or "").strip()
        if user_id:
            return {
                "user_id": user_id,
                "role": "speaker",
                "name": session.get("speaker_name") or session.get("name") or user_id,
                "speaker_id": session.get("speaker_id") or user_id,
                "speaker_name": session.get("speaker_name") or session.get("name") or user_id,
            }
    return None


def _speaker_id(payload: dict | None = None) -> str | None:
    user = _authenticated_speaker()
    if user:
        return (user.get("speaker_id") or user.get("user_id") or "").strip() or None
    if session.get("role") == "speaker":
        speaker_id = (session.get("speaker_id") or session.get("user_id") or "").strip()
        if speaker_id:
            return speaker_id
    if not current_app.config.get("TESTING"):
        return None
    body = payload if payload is not None else (request.get_json(silent=True) or {})
    return (
        request.headers.get("X-Speaker-Id")
        or request.args.get("speaker_id")
        or (body or {}).get("speaker_id")
    )


def _speaker_profile(speaker_id: str) -> dict:
    user = _authenticated_speaker() or {}
    return {
        "speaker_id": speaker_id,
        "speaker_name": user.get("speaker_name") or user.get("name") or speaker_id,
        "role": "speaker",
    }


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _resolved_category(payload: dict) -> str:
    category = str(payload.get("category") or payload.get("topic") or "").strip()
    custom_topic = str(payload.get("custom_topic") or payload.get("customTopic") or "").strip()
    if category.lower() in {"other", "other..."}:
        return custom_topic
    return category


def enhance_abstract_view():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to enhance an abstract", status=401)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")
    abstract = str(payload.get("abstract") or payload.get("text") or "").strip()
    title = str(payload.get("title") or "").strip()
    category = _resolved_category(payload)
    if len(abstract) < 12:
        return _validation_error("Add a short draft abstract before enhancing it.")
    if len(abstract) > 4000:
        return _validation_error("Abstract is too long to enhance.")
    result = enhance_abstract(abstract, title=title, category=category)
    if result.error:
        return jsonify({"error": result.error}), result.status_code

    body = {
        "enhanced_abstract": result.text,
        "abstract": result.text,
        "model": result.model,
    }
    if result.fallback:
        body["fallback"] = True
        body["message"] = result.message
    return jsonify(body), 200


def submit_talk_view():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    missing = [field for field in REQUIRED_SUBMIT_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return _validation_error(f"Missing required fields: {', '.join(missing)}")

    speaker_id = _speaker_id(payload)
    if not speaker_id:
        return _validation_error("Sign in as a speaker to submit a talk")

    title = str(payload["title"]).strip()
    abstract = str(payload["abstract"]).strip()
    category = _resolved_category(payload)
    date = str(payload.get("date") or "").strip()
    start_time = str(payload.get("start_time") or payload.get("start") or "").strip()
    end_time = str(payload.get("end_time") or payload.get("end") or "").strip()
    if str(payload.get("category") or "").strip().lower() in {"other", "other..."} and not category:
        return _validation_error("Enter a custom topic")
    if not title or not abstract or not category:
        return _validation_error("title, abstract, and category cannot be empty")
    try:
        capacity = int(payload["capacity"])
    except (TypeError, ValueError):
        return _validation_error("capacity must be an integer")

    try:
        submission = submit_talk_handler.handle(
            SubmitTalkCommand(
                speaker_id=str(speaker_id),
                title=title,
                abstract=abstract,
                category=category,
                organizer_id=admin_organizer_id(),
                date=date,
                start_time=start_time,
                end_time=end_time,
                capacity=capacity,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 201


@speaker_bp.route("/me", methods=["GET"])
def current_speaker():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to use this portal", status=401)
    return jsonify(_speaker_profile(speaker_id)), 200


@speaker_bp.route("/portal", methods=["GET"])
def speaker_portal():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to use this portal", status=401)
    events = list_speaker_events_handler.handle(ListSpeakerEventsQuery(speaker_id=speaker_id))
    submissions = list_speaker_submissions_handler.handle(
        ListSpeakerSubmissionsQuery(speaker_id=speaker_id, initiated_only=True)
    )
    requests = list_speaker_requests_handler.handle(
        ListSpeakerRequestsQuery(speaker_id=speaker_id, statuses=("pending",))
    )
    return jsonify(
        {
            **_speaker_profile(speaker_id),
            "events": [event_store.speaker_event_payload(item) for item in events],
            "submissions": [item.to_dict() for item in submissions],
            "requests": [item.to_dict() for item in requests],
        }
    ), 200


@speaker_bp.route("/events", methods=["GET"])
def list_my_events():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to view confirmed events")
    events = list_speaker_events_handler.handle(ListSpeakerEventsQuery(speaker_id=speaker_id))
    return jsonify(
        {
            "speaker_id": speaker_id,
            "events": [event_store.speaker_event_payload(item) for item in events],
        }
    ), 200


@speaker_bp.route("/submit", methods=["POST"])
def submit_talk():
    return submit_talk_view()


@speaker_bp.route("/enhance-abstract", methods=["POST"])
def enhance_abstract_route():
    return enhance_abstract_view()


@speaker_bp.route("/submissions", methods=["GET"])
def list_my_submissions():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to view submissions")
    submissions = list_speaker_submissions_handler.handle(
        ListSpeakerSubmissionsQuery(speaker_id=speaker_id)
    )
    return jsonify(
        {
            "speaker_id": speaker_id,
            "submissions": [submission.to_dict() for submission in submissions],
        }
    ), 200


@speaker_bp.route("/submissions/<speaker_id>", methods=["GET"])
def list_submissions(speaker_id: str):
    authenticated = _speaker_id()
    if authenticated:
        speaker_id = authenticated
    speaker_id = (speaker_id or "").strip()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to view submissions")

    submissions = list_speaker_submissions_handler.handle(
        ListSpeakerSubmissionsQuery(speaker_id=speaker_id)
    )
    return jsonify(
        {
            "speaker_id": speaker_id,
            "submissions": [submission.to_dict() for submission in submissions],
        }
    ), 200


@speaker_bp.route("/requests", methods=["GET"])
def list_requests():
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to view requests")
    status = str(request.args.get("status") or "pending").strip().lower()
    statuses = None
    if status in {"pending", "awaiting"}:
        statuses = ("pending",)
    elif status in {"all"}:
        statuses = None
    elif status in {"accepted", "declined"}:
        statuses = (status,)
    else:
        return _validation_error("status must be pending, accepted, declined, or all")
    requests = list_speaker_requests_handler.handle(
        ListSpeakerRequestsQuery(speaker_id=speaker_id, statuses=statuses)
    )
    return jsonify(
        {
            "speaker_id": speaker_id,
            "requests": [item.to_dict() for item in requests],
        }
    ), 200


@speaker_bp.route("/requests/<request_id>/respond", methods=["POST"])
def respond_to_request(request_id: str):
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    speaker_id = _speaker_id(payload)
    if not speaker_id:
        return _validation_error("Sign in as a speaker to respond to a request")

    action = str(payload.get("response") or payload.get("action") or "").strip().lower()
    if action not in {"accept", "decline"}:
        return _validation_error("response must be accept or decline")

    try:
        talk_request = respond_to_talk_request_handler.handle(
            RespondToTalkRequestCommand(
                speaker_id=str(speaker_id),
                request_id=str(request_id).strip(),
                accept=action == "accept",
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(talk_request.to_dict()), 200


@speaker_bp.route("/submissions/<submission_id>/confirm", methods=["POST"])
def confirm_submission(submission_id: str):
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    speaker_id = _speaker_id(payload)
    if not speaker_id:
        return _validation_error("Sign in as a speaker to confirm a talk")
    if payload.get("response") is None and payload.get("action") is None and "confirm" in payload:
        confirm = bool(payload.get("confirm"))
    else:
        action = str(payload.get("response") or payload.get("action") or "confirm").strip().lower()
        if action in {"decline", "reject", "no"}:
            confirm = False
        elif action in {"confirm", "accept", "yes", ""}:
            confirm = True
        else:
            return _validation_error("response must be confirm or decline")
    try:
        submission = confirm_talk_handler.handle(
            ConfirmTalkCommand(
                speaker_id=str(speaker_id),
                submission_id=str(submission_id).strip(),
                confirm=confirm,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200


@speaker_bp.route("/submissions/<submission_id>/restore", methods=["POST"])
def restore_submission(submission_id: str):
    speaker_id = _speaker_id()
    if not speaker_id:
        return _validation_error("Sign in as a speaker to restore a talk")
    try:
        submission = restore_talk_handler.handle(
            RestoreTalkCommand(submission_id=str(submission_id).strip(), speaker_id=str(speaker_id))
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(submission.to_dict()), 200
