from flask import Blueprint, jsonify, request, session

from cqrs import (
    CancelAttendeeRegistrationCommand,
    ClaimWaitlistSeatsCommand,
    JoinWaitlistCommand,
    ListActiveEventsQuery,
    ListApprovedEventsQuery,
    ListAttendeeTicketsQuery,
    LoginCommand,
    RegisterAccountCommand,
    RegisterAttendeeCommand,
    cancel_attendee_registration_handler,
    claim_waitlist_seats_handler,
    join_waitlist_handler,
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
from services.chat import list_messages_for
from services.embeddings import cosine_similarity, embed_text, proposal_document
from services.event_covers import cover_image_url
from services.scheduling import cancellation_window_payload
from services.group_seating import suggest_group_seats
from services.seating import normalize_seat_ids, seating_map_payload
from services.waitlist import (
    WAITLIST_MAX_SEATS,
    attach_waitlist_state,
    waitlist_cards,
    waitlist_seat_cap,
)
from services.topics import catalog_topic_labels
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
        item["cover_image"] = cover_image_url(
            item["topic"], item["title"], seed=event.id
        )
        cards.append(item)
    attach_waitlist_state(cards, _attendee_id())
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
    by_key: dict[str, str] = {}
    for label in catalog_topic_labels():
        by_key[label.lower()] = label
    for card in source:
        topic = (card.get("topic") or "").strip()
        if topic and topic.lower() not in by_key:
            by_key[topic.lower()] = topic
    topics = sorted(by_key.values(), key=str.lower)
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
        item["cover_image"] = cover_image_url(item["topic"], item["title"], seed=event.id)
        item["tickets"] = booking.seats
        item["seat_ids"] = booking.seat_ids
        item["booking_id"] = booking.id
        item["booking_status"] = booking.status
        item.update(cancellation_window_payload(event.date, event.start_time))
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
    added = list(getattr(booking, "added_seat_ids", None) or booking.seat_ids)
    return {
        **booking.to_dict(),
        **_seat_snapshot(booking.event_id),
        "added_seat_ids": added,
        "additional": bool(getattr(booking, "additional", False)),
    }


def _parse_seat_request(payload: dict) -> tuple[int, list[str]]:
    raw_seats = payload.get("seats")
    seat_ids = normalize_seat_ids(
        payload.get("seat_ids")
        or payload.get("seat_numbers")
        or payload.get("selected_seats")
        or (raw_seats if isinstance(raw_seats, (list, tuple)) else None)
    )
    if isinstance(raw_seats, (list, tuple)):
        seats = len(seat_ids)
    elif raw_seats in (None, ""):
        seats = len(seat_ids) or 1
    else:
        try:
            seats = int(raw_seats)
        except (TypeError, ValueError) as exc:
            raise ValueError("seats must be an integer") from exc
    if seat_ids and seats != len(seat_ids):
        raise ValueError("seats must match the number of selected seat IDs")
    if seats < 1:
        raise ValueError("seats must be at least 1")
    return seats, seat_ids


def _book_seats(attendee_id: str, event_id: str, seats: int, seat_ids: list[str] | None = None):
    return register_attendee_handler.handle(
        RegisterAttendeeCommand(
            attendee_id=str(attendee_id),
            event_id=event_id,
            seats=seats,
            seat_ids=seat_ids or None,
        )
    )


@attendee_bp.route("/messages", methods=["GET"])
def list_messages():
    attendee_id = _attendee_id()
    if not attendee_id:
        return _validation_error("Sign in as an attendee to view messages")
    return jsonify(
        {
            "attendee_id": attendee_id,
            "messages": list_messages_for(attendee_id, "attendee"),
        }
    ), 200


@attendee_bp.route("/events", methods=["GET"])
def list_events():
    events = list_active_events_handler.handle(ListActiveEventsQuery())
    return jsonify([event.to_dict() for event in events]), 200


@attendee_bp.route("/events/<event_id>/seats", methods=["GET"])
def event_seat_map(event_id: str):
    event = db.session.get(Event, str(event_id or "").strip())
    if event is None:
        return _validation_error("event not found", status=404)
    return jsonify(seating_map_payload(event, _attendee_id())), 200


@attendee_bp.route("/events/<event_id>/group-seats", methods=["POST"])
def suggest_group_seat_block(event_id: str):
    event = db.session.get(Event, str(event_id or "").strip())
    if event is None:
        return _validation_error("event not found", status=404)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    suggestion = suggest_group_seats(event, payload.get("seats"))
    if not suggestion.get("ok"):
        return _validation_error(
            suggestion.get("error") or "Could not suggest group seats",
            status=int(suggestion.get("status") or 400),
        )
    return jsonify(suggestion), 200


def _request_filters(body: dict | None = None) -> tuple[str, str]:
    payload = body if isinstance(body, dict) else {}
    topic = str(
        request.args.get("topic") or request.args.get("category") or payload.get("topic") or payload.get("category") or ""
    ).strip()
    speaker = str(
        request.args.get("speaker") or request.args.get("speaker_id") or payload.get("speaker") or payload.get("speaker_id") or ""
    ).strip()
    return topic, speaker


@attendee_bp.route("/topics", methods=["GET"])
def list_public_topics():
    options = browse_filter_options()
    return jsonify({"topics": options["topics"]}), 200


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

    try:
        seats, seat_ids = _parse_seat_request(payload)
    except ValueError as exc:
        return _validation_error(str(exc))

    try:
        booking = _book_seats(str(attendee_id), event_id, seats, seat_ids)
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

    try:
        seats, seat_ids = _parse_seat_request(payload)
    except ValueError as exc:
        return _validation_error(str(exc))

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
        booking = _book_seats(attendee_id, event_id, seats, seat_ids)
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)

    return jsonify(_booking_payload(booking)), 201


@attendee_bp.route("/tickets/<booking_id>/cancel", methods=["POST"])
def cancel_ticket(booking_id: str):
    attendee_id = _attendee_id()
    if not attendee_id:
        return _validation_error("Sign in as an attendee to cancel a registration")

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    seat_ids = normalize_seat_ids(payload.get("seat_ids") or payload.get("seat_id"))

    try:
        booking = cancel_attendee_registration_handler.handle(
            CancelAttendeeRegistrationCommand(
                booking_id=str(booking_id or "").strip(),
                attendee_id=str(attendee_id),
                seat_ids=seat_ids or None,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)

    return jsonify(_booking_payload(booking)), 200


def _parse_waitlist_seats(payload: dict, maximum: int) -> int:
    raw = payload.get("seats") if isinstance(payload, dict) else 1
    if raw in (None, ""):
        return 1
    try:
        seats = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("seats must be an integer") from exc
    if seats < 1:
        raise ValueError("seats must be at least 1")
    return min(seats, max(1, maximum))


@attendee_bp.route("/waitlist", methods=["GET"])
def list_waitlist():
    attendee_id = _attendee_id()
    if not attendee_id:
        return _validation_error("Sign in as an attendee to view the waitlist")
    return jsonify({"waitlist": waitlist_cards(attendee_id)}), 200


@attendee_bp.route("/waitlist", methods=["POST"])
def join_waitlist():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return _validation_error("JSON body is required")
    event_id = str(payload.get("event_id") or "").strip()
    if not event_id:
        return _validation_error("event_id cannot be empty")
    attendee_id = _attendee_id(payload)
    if not attendee_id:
        return _validation_error("Sign in as an attendee to join the waitlist")
    event = db.session.get(Event, event_id)
    cap = waitlist_seat_cap(event.capacity if event is not None else WAITLIST_MAX_SEATS)
    try:
        seats = _parse_waitlist_seats(payload, cap)
    except ValueError as exc:
        return _validation_error(str(exc))
    try:
        entry = join_waitlist_handler.handle(
            JoinWaitlistCommand(attendee_id=str(attendee_id), event_id=event_id, seats=seats)
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(entry.to_dict()), 201


@attendee_bp.route("/waitlist/<event_id>/claim", methods=["POST"])
def claim_waitlist(event_id: str):
    attendee_id = _attendee_id()
    if not attendee_id:
        return _validation_error("Sign in as an attendee to claim waitlist seats")
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        payload = {}
    try:
        seats = _parse_waitlist_seats(payload, WAITLIST_MAX_SEATS)
    except ValueError as exc:
        return _validation_error(str(exc))
    try:
        booking = claim_waitlist_seats_handler.handle(
            ClaimWaitlistSeatsCommand(
                attendee_id=str(attendee_id),
                event_id=str(event_id or "").strip(),
                seats=seats,
            )
        )
    except DomainError as exc:
        db.session.rollback()
        return _validation_error(exc.message, status=exc.status)
    return jsonify(_booking_payload(booking)), 201
