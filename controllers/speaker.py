from flask import Blueprint, current_app, jsonify, request

from cqrs import (
    ListSpeakerRequestsQuery,
    ListSpeakerSubmissionsQuery,
    RespondToTalkRequestCommand,
    SubmitTalkCommand,
    list_speaker_requests_handler,
    list_speaker_submissions_handler,
    respond_to_talk_request_handler,
    submit_talk_handler,
)
from cqrs.errors import DomainError
from extensions import db
from cqrs.errors import DomainError
from extensions import db
from services.auth import admin_organizer_id, current_user

speaker_bp = Blueprint("speaker", __name__, url_prefix="/api/speaker")

REQUIRED_SUBMIT_FIELDS = ("title", "abstract", "category", "date", "start_time", "end_time", "capacity")


def _authenticated_speaker() -> dict | None:
    user = current_user()
    if user and user["role"] == "speaker":
        return user
    return None


def _speaker_id(payload: dict | None = None) -> str | None:
    user = _authenticated_speaker()
    if user:
        return user.get("speaker_id") or user["user_id"]
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
    category = str(payload["category"]).strip()
    date = str(payload.get("date") or "").strip()
    start_time = str(payload.get("start_time") or payload.get("start") or "").strip()
    end_time = str(payload.get("end_time") or payload.get("end") or "").strip()
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
    submissions = list_speaker_submissions_handler.handle(
        ListSpeakerSubmissionsQuery(speaker_id=speaker_id)
    )
    requests = list_speaker_requests_handler.handle(
        ListSpeakerRequestsQuery(speaker_id=speaker_id)
    )
    return jsonify(
        {
            **_speaker_profile(speaker_id),
            "submissions": [item.to_dict() for item in submissions],
            "requests": [item.to_dict() for item in requests],
        }
    ), 200


@speaker_bp.route("/submit", methods=["POST"])
def submit_talk():
    return submit_talk_view()


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
    requests = list_speaker_requests_handler.handle(
        ListSpeakerRequestsQuery(speaker_id=speaker_id)
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
