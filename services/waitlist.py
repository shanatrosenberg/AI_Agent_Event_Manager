"""Automated waitlist + first-come, first-served seat-claim agent."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import inspect, text

from extensions import db
from models.chat_message import ChatMessage
from models.event import Event
from models.waitlist import WaitlistEntry

WAITLIST_MAX_SEATS = 10
WAITLIST_ACTIVE = ("waiting", "notified")
WAITLIST_OFFER_KIND = "waitlist_offer"
WAITLIST_OFFER_TEMPLATE = (
    'Seats just opened for "{title}". {available} {label} available now. '
    "Claim them first-come, first-served — the first waitlist client to confirm gets the seats."
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ensure_waitlist_schema() -> None:
    inspector = inspect(db.engine)
    if "waitlist_entries" not in set(inspector.get_table_names()):
        WaitlistEntry.__table__.create(bind=db.engine, checkfirst=True)


def waitlist_seat_cap(capacity: int | None = None) -> int:
    hall = max(1, int(capacity or WAITLIST_MAX_SEATS))
    return min(WAITLIST_MAX_SEATS, hall)


def get_active_entry(attendee_id: str, event_id: str) -> WaitlistEntry | None:
    return (
        WaitlistEntry.query.filter(
            WaitlistEntry.attendee_id == attendee_id,
            WaitlistEntry.event_id == event_id,
            WaitlistEntry.status.in_(WAITLIST_ACTIVE),
        )
        .order_by(WaitlistEntry.created_at.asc())
        .first()
    )


def list_active_for_attendee(attendee_id: str) -> list[WaitlistEntry]:
    return (
        WaitlistEntry.query.filter(
            WaitlistEntry.attendee_id == attendee_id,
            WaitlistEntry.status.in_(WAITLIST_ACTIVE),
        )
        .order_by(WaitlistEntry.created_at.asc())
        .all()
    )


def list_waiting_for_event(event_id: str) -> list[WaitlistEntry]:
    return (
        WaitlistEntry.query.filter(
            WaitlistEntry.event_id == event_id,
            WaitlistEntry.status.in_(WAITLIST_ACTIVE),
        )
        .order_by(WaitlistEntry.created_at.asc())
        .all()
    )


def attach_waitlist_state(cards: list[dict], attendee_id: str | None) -> list[dict]:
    from models.booking import Booking

    user = (attendee_id or "").strip()
    if not user or not cards:
        for card in cards:
            card.setdefault("waitlisted", False)
            card.setdefault("waitlist_seats", 0)
            card.setdefault("already_booked", False)
        return cards
    rows = list_active_for_attendee(user)
    by_event = {row.event_id: row for row in rows}
    booked = {
        row.event_id
        for row in Booking.query.filter_by(attendee_id=user, status="confirmed").all()
    }
    for card in cards:
        entry = by_event.get(card.get("id"))
        card["waitlisted"] = entry is not None
        card["waitlist_seats"] = entry.seats_requested if entry else 0
        card["already_booked"] = card.get("id") in booked
    return cards


def waitlist_cards(attendee_id: str) -> list[dict]:
    cards = []
    for entry in list_active_for_attendee(attendee_id):
        event = entry.event or db.session.get(Event, entry.event_id)
        remaining = event.remaining_seats if event is not None else 0
        max_claim = max(0, min(entry.seats_requested, remaining))
        item = entry.to_dict()
        item["title"] = event.title if event is not None else "Session"
        item["date"] = event.date if event is not None else ""
        item["start_time"] = event.start_time if event is not None else ""
        item["remaining_seats"] = remaining
        item["max_claim"] = max_claim
        item["can_claim"] = remaining > 0 and entry.status in WAITLIST_ACTIVE
        cards.append(item)
    return cards


def enrich_waitlist_messages(messages: list[dict], attendee_id: str) -> list[dict]:
    entries = {row.event_id: row for row in list_active_for_attendee(attendee_id)}
    enriched = []
    for note in messages:
        item = dict(note)
        if item.get("kind") == WAITLIST_OFFER_KIND and item.get("event_id"):
            entry = entries.get(item["event_id"])
            event = db.session.get(Event, item["event_id"])
            remaining = event.remaining_seats if event is not None else 0
            requested = entry.seats_requested if entry else remaining
            item["remaining_seats"] = remaining
            item["seats_requested"] = requested
            item["max_claim"] = max(0, min(requested, remaining))
            item["can_claim"] = remaining > 0 and entry is not None
            item["event_title"] = event.title if event is not None else item.get("subject")
        enriched.append(item)
    return enriched


def notify_seats_released(event: Event, released: int) -> dict:
    available = event.remaining_seats if event is not None else 0
    if released < 1 or available < 1 or event is None:
        return {"notified": 0, "available": available}
    waiting = list_waiting_for_event(event.id)
    if not waiting:
        return {"notified": 0, "available": available}

    from services.auth import admin_organizer_id

    title = (event.title or "this session").strip() or "this session"
    label = "seat is" if available == 1 else "seats are"
    body = WAITLIST_OFFER_TEMPLATE.format(title=title, available=available, label=label)
    now = utc_now()
    created = 0
    for entry in waiting:
        entry.status = "notified"
        entry.notified_at = now
        entry.offer_seats = available
        db.session.add(
            ChatMessage(
                id=str(uuid4()),
                recipient_id=entry.attendee_id,
                recipient_role="attendee",
                sender_id=event.organizer_id or admin_organizer_id(),
                sender_role="organizer",
                subject="Seats available",
                event_id=event.id,
                kind=WAITLIST_OFFER_KIND,
                body=body,
            )
        )
        created += 1
    db.session.commit()
    return {"notified": created, "available": available}


def cancel_event_waitlist(event_id: str) -> int:
    rows = list_waiting_for_event(event_id)
    for entry in rows:
        entry.status = "cancelled"
    return len(rows)
