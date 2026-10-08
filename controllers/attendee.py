from flask import Blueprint, jsonify, request, session

from cqrs import (
    ListActiveEventsQuery,
    ListApprovedEventsQuery,
    ListAttendeeTicketsQuery,
    LoginCommand,
    RegisterAccountCommand,
    RegisterAttendeeCommand,
    list_active_events_handler,
    list_approved_events_handler,
    list_attendee_tickets_handler,
    login_handler,
    register_account_handler,
    register_attendee_handler,
)
from cqrs.errors import DomainError
from extensions import db
from models.event import Event
from models.submission import TalkSubmission
from services.auth import current_user, establish_session
from services.embeddings import cosine_similarity, embed_text, proposal_document
from services.vector_store import search_similar

attendee_bp = Blueprint("attendee", __name__, url_prefix="/api/attendee")

REQUIRED_REGISTER_FIELDS = ("event_id",)


def _attendee_id(payload: dict | None = None) -> str | None:
    user = current_user()
    if user and user.get("role") == "attendee":
        return user.get("user_id")
    if session.get("role") == "attendee":
        return (session.get("user_id") or "").strip() or None
    body = payload if payload is not None else (request.get_json(silent=True) or {})
    return (
        request.headers.get("X-Attendee-Id")
        or request.args.get("attendee_id")
        or (body or {}).get("attendee_id")
    )


def _topic_map(event_ids: list[str]) -> dict[str, str]:
    if not event_ids:
        return {}
    rows = TalkSubmission.query.filter(TalkSubmission.event_id.in_(event_ids)).all()
    return {row.event_id: (row.category or "").strip() for row in rows if row.event_id}


def browse_event_cards(topic: str | None = None, speaker: str | None = None):
    events = list_approved_events_handler.handle(
        ListApprovedEventsQuery(topic=topic, speaker=speaker)
    )
    topics = _topic_map([event.id for event in events])
    cards = []
    for event in events:
        item = event.to_dict()
        item["topic"] = topics.get(event.id) or "Session"
        cards.append(item)
    topic_key = (topic or "").strip().lower()
    speaker_key = (speaker or "").strip().lower()
    if topic_key:
        cards = [card for card in cards if (card.get("topic") or "").strip().lower() == topic_key]
    if speaker_key:
        cards = [
            card
            for card in cards
            if speaker_key
            in {
                (card.get("speaker_id") or "").strip().lower(),
                (card.get("speaker_name") or "").strip().lower(),
            }
        ]
    return cards


def browse_filter_options(cards: list[dict] | None = None) -> dict[str, list[dict]]:
    source = cards if cards is not None else browse_event_cards()
    topics = sorted({(card.get("topic") or "Session").strip() for card in source if card.get("topic")})
    speakers = []
    seen = set()
    for card in source:
        speaker_id = (card.get("speaker_id") or "").strip()
        speaker_name = (card.get("speaker_name") or speaker_id or "Guest speaker").strip()
        key = speaker_id or speaker_name.lower()
        if not key or key in seen:
            continue
        seen.add(key)
        speakers.append({"id": speaker_id or speaker_name, "name": speaker_name})
    speakers.sort(key=lambda item: item["name"].lower())
    return {"topics": topics, "speakers": speakers}


def search_browse_event_cards(
    query: str,
    limit: int = 24,
    topic: str | None = None,
    speaker: str | None = None,
) -> list[dict]:
    cards = browse_event_cards(topic=topic, speaker=speaker)
    text = (query or "").strip()
    if not text:
        return cards
    try:
        parsed_limit = min(40, max(1, int(limit)))
    except (TypeError, ValueError):
        parsed_limit = 24
    hits = search_similar(
        text,
        limit=max(parsed_limit, 20),
        source_types=("event",),
        backfill=False,
    )
    by_id = {card["id"]: card for card in cards}
    by_title: dict[str, list[dict]] = {}
    by_speaker: dict[str, list[dict]] = {}
    for card in cards:
        by_title.setdefault((card.get("title") or "").strip().lower(), []).append(card)
        speaker_id = (card.get("speaker_id") or "").strip()
        if speaker_id:
            by_speaker.setdefault(speaker_id, []).append(card)
    ranked: list[dict] = []
    seen: set[str] = set()
    for hit in hits:
        candidates: list[dict] = []
        if hit.get("source_type") == "event" and hit.get("id") in by_id:
            candidates.append(by_id[hit["id"]])
        event_id = hit.get("event_id")
        if event_id and event_id in by_id:
            candidates.append(by_id[event_id])
        title_key = (hit.get("title") or "").strip().lower()
        if title_key in by_title:
            candidates.extend(by_title[title_key])
        speaker_id = (hit.get("speaker_id") or "").strip()
        if hit.get("source_type") == "speaker" and speaker_id in by_speaker:
            candidates.extend(by_speaker[speaker_id])
        for card in candidates:
            if card["id"] in seen:
                continue
            seen.add(card["id"])
            ranked.append({**card, "score": hit.get("score")})
            if len(ranked) >= parsed_limit:
                return ranked
    if ranked:
        return ranked
    query_vector = embed_text(text)
    scored = []
    for card in cards:
        document = proposal_document(
            title=card.get("title") or "",
            abstract=card.get("description") or "",
            category=card.get("topic") or "",
            speaker_name=card.get("speaker_name") or card.get("speaker_id") or "",
        )
        score = cosine_similarity(query_vector, embed_text(document))
        if score > 0:
            scored.append((score, card))
    scored.sort(key=lambda item: item[0], reverse=True)
    return [{**card, "score": round(float(score), 4)} for score, card in scored[:parsed_limit]]


def attendee_ticket_cards(attendee_id: str) -> list[dict]:
    bookings = list_attendee_tickets_handler.handle(ListAttendeeTicketsQuery(attendee_id=attendee_id))
    event_ids = [booking.event_id for booking in bookings if booking.event_id]
    topics = {}
    if event_ids:
        rows = TalkSubmission.query.filter(TalkSubmission.event_id.in_(event_ids)).all()
        topics = {row.event_id: (row.category or "").strip() for row in rows if row.event_id}
    cards = []
    for booking in bookings:
        event = booking.event
        if event is None:
            continue
        item = event.to_dict()
        item["topic"] = topics.get(event.id) or "Session"
        item["tickets"] = booking.seats
        item["booking_id"] = booking.id
        item["booking_status"] = booking.status
        cards.append(item)
    return cards


def _validation_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def _seat_snapshot(event_id: str) -> dict:
    event = db.session.get(Event, event_id)
    if event is None:
        return {}
    remaining = event.remaining_seats
    return {
        "remaining_seats": remaining,
        "seats_booked": event.seats_booked,
        "capacity": event.capacity,
        "sold_out": remaining <= 0,
        "last_seats": 0 < remaining <= 10,
    }


def _booking_payload(booking) -> dict:
    return {**booking.to_dict(), **_seat_snapshot(booking.event_id)}


def _book_seats(attendee_id: str, event_id: str, seats: int):
    return register_attendee_handler.handle(
        RegisterAttendeeCommand(
            attendee_id=str(attendee_id),
            event_id=event_id,
            seats=seats,
        )
    )


@attendee_bp.route("/events", methods=["GET"])
def list_events():
    events = list_active_events_handler.handle(ListActiveEventsQuery())
    return jsonify([event.to_dict() for event in events]), 200


def _request_filters(body: dict | None = None) -> tuple[str, str]:
    payload = body if isinstance(body, dict) else {}
    topic = str(
        request.args.get("topic") or request.args.get("category") or payload.get("topic") or payload.get("category") or ""
    ).strip()
    speaker = str(
        request.args.get("speaker") or request.args.get("speaker_id") or payload.get("speaker") or payload.get("speaker_id") or ""
    ).strip()
    return topic, speaker


@attendee_bp.route("/approved", methods=["GET"])
def list_approved_events():
    topic, speaker = _request_filters()
    cards = browse_event_cards(topic=topic or None, speaker=speaker or None)
    return jsonify(cards), 200


@attendee_bp.route("/search", methods=["GET", "POST"])
def search_talks():
    body = request.get_json(silent=True) or {}
    query = str(
        request.args.get("q") or request.args.get("query") or body.get("query") or body.get("q") or ""
    ).strip()
    if not query:
        return _validation_error("query is required")
    limit = request.args.get("limit", body.get("limit", 24))
    topic, speaker = _request_filters(body)
    results = search_browse_event_cards(
        query,
        limit=limit,
        topic=topic or None,
        speaker=speaker or None,
    )
    return jsonify({"query": query, "count": len(results), "results": results}), 200


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
        booking = _book_seats(str(attendee_id), event_id, seats)
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)

    return jsonify(_booking_payload(booking)), 201


@attendee_bp.route("/tickets", methods=["POST"])
def buy_tickets():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")

    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        return _validation_error("event_id cannot be empty")

    seats_value = payload.get("seats", 1)
    try:
        seats = int(seats_value)
    except (TypeError, ValueError):
        return _validation_error("seats must be an integer")
    if seats < 1:
        return _validation_error("seats must be at least 1")

    customer = str(payload.get("customer") or "").strip().lower()
    user_id = str(payload.get("user_id") or payload.get("attendee_id") or "").strip()
    password = str(payload.get("password") or "")
    name = str(payload.get("name") or "").strip()

    try:
        if customer == "new":
            account = register_account_handler.handle(
                RegisterAccountCommand(
                    user_id=user_id,
                    password=password,
                    role="attendee",
                    name=name,
                )
            )
            establish_session(account["user_id"], account["role"], account.get("name"))
            attendee_id = account["user_id"]
        elif customer == "existing":
            account = login_handler.handle(
                LoginCommand(user_id=user_id, password=password, role="attendee")
            )
            establish_session(account["user_id"], account["role"], account.get("name"))
            attendee_id = account["user_id"]
        else:
            attendee_id = _attendee_id(payload)
            if not attendee_id:
                return _validation_error("Choose Existing Customer or New Customer to buy tickets")
        booking = _book_seats(attendee_id, event_id, seats)
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)

    return jsonify(_booking_payload(booking)), 201
