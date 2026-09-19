from flask import Blueprint, jsonify, request

from cqrs import (
    CreateEventCommand,
    ListOrganizerEventsQuery,
    create_event_handler,
    list_organizer_events_handler,
)

organizer_bp = Blueprint("organizer", __name__, url_prefix="/api/organizer")

REQUIRED_CREATE_FIELDS = ("title", "description", "date", "capacity")


def _organizer_id() -> str | None:
    return (
        request.headers.get("X-Organizer-Id")
        or request.args.get("organizer_id")
        or (request.get_json(silent=True) or {}).get("organizer_id")
    )


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@organizer_bp.route("/events", methods=["POST"])
def create_event():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    missing = [field for field in REQUIRED_CREATE_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return _validation_error(f"Missing required fields: {', '.join(missing)}")

    organizer_id = _organizer_id()
    if not organizer_id:
        return _validation_error("organizer_id is required (JSON body or X-Organizer-Id header)")

    try:
        capacity = int(payload["capacity"])
    except (TypeError, ValueError):
        return _validation_error("capacity must be an integer")

    if capacity < 1:
        return _validation_error("capacity must be at least 1")

    title = str(payload["title"]).strip()
    description = str(payload["description"]).strip()
    date = str(payload["date"]).strip()
    if not title or not date:
        return _validation_error("title and date cannot be empty")

    event = create_event_handler.handle(
        CreateEventCommand(
            organizer_id=str(organizer_id),
            title=title,
            description=description,
            date=date,
            capacity=capacity,
        )
    )
    return jsonify(event.to_dict()), 201


@organizer_bp.route("/events", methods=["GET"])
def list_events():
    organizer_id = request.headers.get("X-Organizer-Id") or request.args.get("organizer_id")
    if not organizer_id:
        return _validation_error("organizer_id is required (query param or X-Organizer-Id header)")

    events = list_organizer_events_handler.handle(
        ListOrganizerEventsQuery(organizer_id=organizer_id)
    )
    return jsonify([event.to_dict() for event in events]), 200
