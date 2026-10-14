"""Load a realistic conference program into the configured database.

    python scripts/seed.py
    python scripts/seed.py --reset
    flask --app main seed --reset
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from extensions import db
from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import TalkSubmission
from models.talk_request import TalkRequest
from services.auth import admin_organizer_id, ensure_admin_organizer
from services.seating import assign_open_seats

SEED_PASSWORD = "EventDemo!2026"

SPEAKERS = (
    {"id": "spk-maya", "name": "Maya Cohen"},
    {"id": "spk-daniel", "name": "Daniel Levi"},
    {"id": "spk-noa", "name": "Noa Ben-David"},
    {"id": "spk-omar", "name": "Omar Hassan"},
    {"id": "spk-lina", "name": "Lina Park"},
)

EVENTS = (
    {
        "id": "evt-open-keynote",
        "speaker_id": "spk-maya",
        "title": "Opening Keynote: Building the Agent-Native Conference",
        "description": "How autonomous reviewers, seat maps, and an event-sourced program board come together for a live multi-track summit. Maya walks through the architecture we use to keep organizers in control while agents do the first pass.",
        "date": "2026-11-12",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 300,
        "seats_booked": 48,
        "status": "approved",
        "category": "ai",
    },
    {
        "id": "evt-open-cqrs",
        "speaker_id": "spk-daniel",
        "title": "Hands-on CQRS with Flask and an Event Store",
        "description": "A workshop that turns talk proposals into commands, projections, and an organizer dashboard. Attendees leave with a working Flask command/query split they can take back to their own event platforms.",
        "date": "2026-11-12",
        "start_time": "10:30",
        "end_time": "12:00",
        "capacity": 100,
        "seats_booked": 22,
        "status": "approved",
        "category": "architecture",
    },
    {
        "id": "evt-open-rag",
        "speaker_id": "spk-noa",
        "title": "Retrieval That Does Not Repeat Last Year's Keynote",
        "description": "A practical RAG design for program uniqueness: embed titles and abstracts, rank overlap, and flag redundant talks before they hit the schedule.",
        "date": "2026-11-13",
        "start_time": "09:00",
        "end_time": "10:15",
        "capacity": 50,
        "seats_booked": 14,
        "status": "approved",
        "category": "ai",
    },
    {
        "id": "evt-open-security",
        "speaker_id": "spk-omar",
        "title": "Zero-Trust Ticketing for Public Event Platforms",
        "description": "Identity isolation, least-privilege booking APIs, and secret handling when organizers, speakers, and attendees share one cloud.",
        "date": "2026-11-13",
        "start_time": "14:00",
        "end_time": "15:30",
        "capacity": 100,
        "seats_booked": 31,
        "status": "approved",
        "category": "architecture",
    },
    {
        "id": "evt-open-edge",
        "speaker_id": "spk-lina",
        "title": "Edge AI Captions for Hybrid Halls",
        "description": "On-device summarization and privacy-preserving captions when the venue Wi-Fi cannot be trusted. Includes a live demo on a 50-seat hall.",
        "date": "2026-11-14",
        "start_time": "11:00",
        "end_time": "12:00",
        "capacity": 50,
        "seats_booked": 9,
        "status": "approved",
        "category": "ai",
    },
    {
        "id": "evt-low-observability",
        "speaker_id": "spk-daniel",
        "title": "Seeing the Program: Observability for CQRS Event Stores",
        "description": "Traces, metrics, and audit logs across TalkProposed to TalkApproved. Almost full — this 50-seat hall is down to the last few chairs.",
        "date": "2026-11-14",
        "start_time": "14:00",
        "end_time": "15:00",
        "capacity": 50,
        "seats_booked": 43,
        "status": "approved",
        "category": "architecture",
    },
    {
        "id": "evt-low-platform",
        "speaker_id": "spk-lina",
        "title": "Platform Engineering Lightning for Conference Ops",
        "description": "Golden paths for proposals and self-service halls. Only a handful of seats remain in this compact session.",
        "date": "2026-11-15",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 50,
        "seats_booked": 46,
        "status": "approved",
        "category": "architecture",
    },
    {
        "id": "evt-sold-memory",
        "speaker_id": "spk-maya",
        "title": "Agent Memory Workshop: What to Keep, What to Forget",
        "description": "A sold-out lab on memory, tool traces, and human escalation. Every seat in the 50-person hall is reserved.",
        "date": "2026-11-15",
        "start_time": "11:00",
        "end_time": "12:30",
        "capacity": 50,
        "seats_booked": 50,
        "status": "approved",
        "category": "ai",
    },
    {
        "id": "evt-sold-ethics",
        "speaker_id": "spk-omar",
        "title": "AI Ethics Roundtable: Who Approves the Approver?",
        "description": "A packed 100-seat hall on accountability for autonomous review agents. Registration is closed.",
        "date": "2026-11-16",
        "start_time": "16:00",
        "end_time": "17:30",
        "capacity": 100,
        "seats_booked": 100,
        "status": "approved",
        "category": "community",
    },
    {
        "id": "evt-cancelled-mixer",
        "speaker_id": "spk-noa",
        "title": "Harbor Evening Mixer",
        "description": "Cancelled after a venue double-booking. Kept on the organizer program as a cancelled session so history stays visible.",
        "date": "2026-11-12",
        "start_time": "18:00",
        "end_time": "20:00",
        "capacity": 100,
        "seats_booked": 0,
        "status": "cancelled",
        "category": "community",
    },
    {
        "id": "evt-cancelled-ama",
        "speaker_id": "spk-omar",
        "title": "Sponsor AMA: Cloud Security in Public Programs",
        "description": "The speaker cannot travel. The session is cancelled; five courtesy reservations were released from the public catalog.",
        "date": "2026-11-16",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 50,
        "seats_booked": 5,
        "status": "cancelled",
        "category": "architecture",
    },
    {
        "id": "evt-deleted-duplicate",
        "speaker_id": "spk-maya",
        "title": "Duplicate Keynote Slot (removed)",
        "description": "Soft-deleted duplicate of the opening keynote. Retained for audit history and not shown to attendees.",
        "date": "2026-11-12",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 300,
        "seats_booked": 0,
        "status": "deleted",
        "category": "ai",
    },
    {
        "id": "evt-deleted-walkthrough",
        "speaker_id": "spk-daniel",
        "title": "Old Venue Walkthrough",
        "description": "Removed after the venue changed. Soft-deleted so organizers can still inspect the original date and time.",
        "date": "2026-10-20",
        "start_time": "10:00",
        "end_time": "11:00",
        "capacity": 50,
        "seats_booked": 0,
        "status": "deleted",
        "category": "architecture",
    },
)


def _clear_program_rows() -> None:
    Booking.query.delete()
    TalkRequest.query.delete()
    TalkSubmission.query.delete()
    Event.query.delete()
    StoredEvent.query.delete()
    Speaker.query.delete()
    Attendee.query.delete()
    db.session.commit()


def _upsert_speaker(item: dict[str, str]) -> Speaker:
    speaker = db.session.get(Speaker, item["id"]) or Speaker(id=item["id"])
    speaker.name = item["name"]
    speaker.set_password(SEED_PASSWORD)
    db.session.add(speaker)
    return speaker


def _attendee(index: int) -> Attendee:
    attendee_id = f"att-seed-{index:02d}"
    attendee = db.session.get(Attendee, attendee_id) or Attendee(id=attendee_id)
    attendee.name = f"Attendee {index:02d}"
    attendee.set_password(SEED_PASSWORD)
    db.session.add(attendee)
    return attendee


def _book_seats(event: Event, attendees: list[Attendee], seats: int) -> list[Booking]:
    if seats <= 0:
        event.seats_booked = 0
        return []
    labels = assign_open_seats(event.capacity, [], seats)
    bookings: list[Booking] = []
    remaining = list(labels)
    for index, attendee in enumerate(attendees):
        if not remaining:
            break
        chunk = max(1, seats // max(1, len(attendees)))
        taken = remaining[:chunk] if index < len(attendees) - 1 else remaining
        remaining = remaining[len(taken) :]
        booking = Booking(
            id=str(uuid4()),
            attendee_id=attendee.id,
            event_id=event.id,
            seats=len(taken),
            seat_labels=taken,
            status="confirmed",
        )
        db.session.add(booking)
        bookings.append(booking)
    event.seats_booked = sum(item.seats for item in bookings)
    return bookings


def _submission_for(event: Event, organizer_id: str) -> TalkSubmission:
    spec = next(item for item in EVENTS if item["id"] == event.id)
    row = TalkSubmission(
        id=str(uuid4()),
        speaker_id=event.speaker_id,
        organizer_id=organizer_id,
        title=event.title,
        abstract=event.description,
        category=spec["category"],
        date=event.date,
        start_time=event.start_time,
        end_time=event.end_time,
        capacity=event.capacity,
        status="approved" if event.status == "approved" else event.status,
        ai_assessment={
            "status": "complete",
            "innovation_score": 88 if spec["category"] == "ai" else 74,
            "innovation_badge": "High Innovation" if spec["category"] == "ai" else "Moderate Novelty",
            "summary": f"Seeded uniqueness review for {event.title}.",
        },
        event_id=event.id,
    )
    db.session.add(row)
    return row


def seed_database(*, reset: bool = False) -> dict[str, int]:
    ensure_admin_organizer()
    organizer_id = admin_organizer_id()
    if reset:
        _clear_program_rows()
        ensure_admin_organizer()

    speakers = [_upsert_speaker(item) for item in SPEAKERS]
    attendees = [_attendee(index) for index in range(1, 21)]
    db.session.flush()

    events: list[Event] = []
    for spec in EVENTS:
        event = Event(
            id=spec["id"],
            organizer_id=organizer_id,
            speaker_id=spec["speaker_id"],
            title=spec["title"],
            description=spec["description"],
            date=spec["date"],
            start_time=spec["start_time"],
            end_time=spec["end_time"],
            capacity=spec["capacity"],
            seats_booked=0,
            status=spec["status"],
        )
        db.session.add(event)
        events.append(event)
        _submission_for(event, organizer_id)
    db.session.flush()

    bookings = 0
    for event, spec in zip(events, EVENTS):
        created = _book_seats(event, attendees, int(spec["seats_booked"]))
        bookings += len(created)

    db.session.commit()
    return {
        "speakers": len(speakers),
        "attendees": len(attendees),
        "events": len(events),
        "bookings": bookings,
        "open_events": sum(1 for item in EVENTS if item["status"] == "approved" and item["capacity"] - item["seats_booked"] > 10),
        "low_capacity_events": sum(1 for item in EVENTS if item["status"] == "approved" and 0 < item["capacity"] - item["seats_booked"] <= 10),
        "sold_out_events": sum(1 for item in EVENTS if item["status"] == "approved" and item["seats_booked"] >= item["capacity"]),
        "cancelled_events": sum(1 for item in EVENTS if item["status"] == "cancelled"),
        "deleted_events": sum(1 for item in EVENTS if item["status"] == "deleted"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed a realistic conference program.")
    parser.add_argument("--reset", action="store_true", help="Clear program rows before inserting.")
    args = parser.parse_args()
    from main import create_app

    app = create_app({"ASSESSMENT_AGENT_AUTOSTART": False})
    with app.app_context():
        from cqrs.store import ensure_event_store_schema
        from services.auth import (
            ensure_event_schedule_columns,
            ensure_event_speaker_column,
            ensure_password_hash_columns,
            ensure_talk_portal_schema,
        )
        from services.seating import ensure_booking_seat_schema
        from services.waitlist import ensure_waitlist_schema

        db.create_all()
        ensure_password_hash_columns()
        ensure_event_speaker_column()
        ensure_event_schedule_columns()
        ensure_talk_portal_schema()
        ensure_event_store_schema()
        ensure_booking_seat_schema()
        ensure_waitlist_schema()
        summary = seed_database(reset=True)
        print("Seeded conference program:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        print(f"  demo password: {SEED_PASSWORD}")


if __name__ == "__main__":
    main()
