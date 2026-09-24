from flask import Blueprint, jsonify, request

from cqrs import (
    ListActiveEventsQuery,
    ListApprovedEventsQuery,
    RegisterAttendeeCommand,
    list_active_events_handler,
    list_approved_events_handler,
    register_attendee_handler,
)
from cqrs.errors import DomainError
from extensions import db

attendee_bp = Blueprint("attendee", __name__, url_prefix="/api/attendee")

REQUIRED_REGISTER_FIELDS = ("event_id",)


def _attendee_id(payload: dict | None = None) -> str | None:
    body = payload if payload is not None else (request.get_json(silent=True) or {})
    return (
        request.headers.get("X-Attendee-Id")
        or request.args.get("attendee_id")
        or (body or {}).get("attendee_id")
    )


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


@attendee_bp.route("/events", methods=["GET"])
def list_events():
    events = list_active_events_handler.handle(ListActiveEventsQuery())
    return jsonify([event.to_dict() for event in events]), 200


@attendee_bp.route("/approved", methods=["GET"])
def list_approved_events():
    events = list_approved_events_handler.handle(ListApprovedEventsQuery())
    return jsonify([event.to_dict() for event in events]), 200


@attendee_bp.route("/register", methods=["POST"])
def register():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    missing = [field for field in REQUIRED_REGISTER_FIELDS if payload.get(field) in (None, "")]
    if missing:
        return _validation_error(f"Missing required fields: {', '.join(missing)}")

    attendee_id = _attendee_id(payload)
    if not attendee_id:
        return _validation_error("attendee_id is required (JSON body, query param, or X-Attendee-Id header)")

    event_id = str(payload["event_id"]).strip()
    if not event_id:
        return _validation_error("event_id cannot be empty")

    seats_value = payload.get("seats", 1)
    try:
        seats = int(seats_value)
    except (TypeError, ValueError):
        return _validation_error("seats must be an integer")

    if seats < 1:
        return _validation_error("seats must be at least 1")

    try:
        booking = register_attendee_handler.handle(
            RegisterAttendeeCommand(
                attendee_id=str(attendee_id),
                event_id=event_id,
                seats=seats,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)

    return jsonify(booking.to_dict()), 201
