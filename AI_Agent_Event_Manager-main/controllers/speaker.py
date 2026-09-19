from flask import Blueprint, jsonify, request

from cqrs import (
    ListSpeakerSubmissionsQuery,
    SubmitTalkCommand,
    list_speaker_submissions_handler,
    submit_talk_handler,
)

speaker_bp = Blueprint("speaker", __name__, url_prefix="/api/speaker")

REQUIRED_SUBMIT_FIELDS = ("title", "abstract", "category")


def _speaker_id(payload: dict | None = None) -> str | None:
    body = payload if payload is not None else (request.get_json(silent=True) or {})
    return (
        request.headers.get("X-Speaker-Id")
        or request.args.get("speaker_id")
        or (body or {}).get("speaker_id")
    )


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@speaker_bp.route("/submit", methods=["POST"])
def submit_talk():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    missing = [field for field in REQUIRED_SUBMIT_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return _validation_error(f"Missing required fields: {', '.join(missing)}")

    speaker_id = _speaker_id(payload)
    if not speaker_id:
        return _validation_error("speaker_id is required (JSON body or X-Speaker-Id header)")

    title = str(payload["title"]).strip()
    abstract = str(payload["abstract"]).strip()
    category = str(payload["category"]).strip()
    if not title or not abstract or not category:
        return _validation_error("title, abstract, and category cannot be empty")

    submission = submit_talk_handler.handle(
        SubmitTalkCommand(
            speaker_id=str(speaker_id),
            title=title,
            abstract=abstract,
            category=category,
        )
    )
    return jsonify(submission.to_dict()), 201


@speaker_bp.route("/submissions/<speaker_id>", methods=["GET"])
def list_submissions(speaker_id: str):
    speaker_id = (speaker_id or "").strip()
    if not speaker_id:
        return _validation_error("speaker_id is required")

    submissions = list_speaker_submissions_handler.handle(
        ListSpeakerSubmissionsQuery(speaker_id=speaker_id)
    )
    return jsonify(
        {
            "speaker_id": speaker_id,
            "submissions": [submission.to_dict() for submission in submissions],
        }
    ), 200
