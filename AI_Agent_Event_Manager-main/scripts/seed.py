"""Load sample Event Management data into the configured database (Somee MS SQL).

Run from the project root so ``.env`` and package imports resolve:

    python scripts/seed.py
    python scripts/seed.py --reset
    flask --app main seed
    flask --app main seed --reset

``--reset`` removes only seed-owned rows (and API rows attached to those
identities), then inserts the sample set again. Existing non-seed data is left
alone on a normal run.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect, text

from extensions import db
from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.organizer import Organizer
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import TalkSubmission

SEED_PASSWORD = "EventDemo!2026"

# Stable IDs so API calls can reuse the same organizers / speakers / attendees.
ORGANIZERS = [
    {"id": "org-summit", "name": "Tech Summit Israel"},
    {"id": "org-meetup", "name": "Haifa Dev Meetup"},
    {"id": "org-campus", "name": "Campus Innovation Lab"},
]

SPEAKERS = [
    {"id": "spk-maya", "name": "Maya Cohen"},
    {"id": "spk-daniel", "name": "Daniel Levi"},
    {"id": "spk-noa", "name": "Noa Ben-David"},
    {"id": "spk-omar", "name": "Omar Hassan"},
]

ATTENDEES = [
    {"id": "att-noah", "name": "Noah Adler"},
    {"id": "att-lia", "name": "Lia Mizrahi"},
    {"id": "att-yonatan", "name": "Yonatan Peretz"},
    {"id": "att-sara", "name": "Sara Klein"},
    {"id": "att-amir", "name": "Amir Dahan"},
]

EVENTS = [
    {
        "id": "a1e00000-0000-4000-8000-000000000001",
        "organizer_id": "org-summit",
        "title": "AI Agents Summit 2026",
        "description": "A full-day program on autonomous agents, CQRS, and production event systems.",
        "date": "2026-10-15",
        "capacity": 80,
        "seats_booked": 5,
        "status": "active",
    },
    {
        "id": "a1e00000-0000-4000-8000-000000000002",
        "organizer_id": "org-meetup",
        "title": "Building Event Systems with Flask",
        "description": "Hands-on workshop covering commands, queries, and an SQLAlchemy event store.",
        "date": "2026-10-22",
        "capacity": 40,
        "seats_booked": 3,
        "status": "active",
    },
    {
        "id": "a1e00000-0000-4000-8000-000000000003",
        "organizer_id": "org-campus",
        "title": "Campus AI Night",
        "description": "Lightning talks from students and local engineers building AI-assisted products.",
        "date": "2026-11-03",
        "capacity": 50,
        "seats_booked": 1,
        "status": "active",
    },
    {
        "id": "a1e00000-0000-4000-8000-000000000004",
        "organizer_id": "org-campus",
        "title": "Intro to RAG",
        "description": "A compact session on retrieval-augmented generation for conference abstracts.",
        "date": "2026-09-30",
        "capacity": 12,
        "seats_booked": 12,
        "status": "active",
    },
    {
        "id": "a1e00000-0000-4000-8000-000000000005",
        "organizer_id": "org-meetup",
        "title": "Legacy Monoliths Workshop",
        "description": "Cancelled due to speaker travel issues. Use this row to test inactive events.",
        "date": "2026-11-05",
        "capacity": 30,
        "seats_booked": 0,
        "status": "cancelled",
    },
]

SUBMISSIONS = [
    {
        "id": "b2e00000-0000-4000-8000-000000000001",
        "speaker_id": "spk-maya",
        "title": "Building Autonomous Event Agents",
        "abstract": (
            "How a background agent can assess talk quality, check topic relevance, "
            "and queue human review without blocking the speaker API."
        ),
        "category": "architecture",
        "status": "under_review",
        "ai_assessment": {
            "status": "queued",
            "quality_score": 42,
            "summary": "Placeholder assessment seeded for local and Somee testing.",
            "queued_for_background_agent": True,
            "source": "seed",
        },
    },
    {
        "id": "b2e00000-0000-4000-8000-000000000002",
        "speaker_id": "spk-daniel",
        "title": "RAG for Conference Abstracts",
        "abstract": (
            "A practical retrieval pipeline that embeds speaker bios and abstracts "
            "so organizers can find overlapping or complementary talks."
        ),
        "category": "ai",
        "status": "under_review",
        "ai_assessment": {
            "status": "queued",
            "quality_score": 36,
            "summary": "Placeholder assessment seeded for local and Somee testing.",
            "queued_for_background_agent": True,
            "source": "seed",
        },
    },
    {
        "id": "b2e00000-0000-4000-8000-000000000003",
        "speaker_id": "spk-noa",
        "title": "Inclusive Event Design",
        "abstract": (
            "Designing capacity, seating, and session formats so first-time attendees "
            "and experienced engineers both get value from the same program."
        ),
        "category": "community",
        "status": "pending_assessment",
        "ai_assessment": {},
    },
    {
        "id": "b2e00000-0000-4000-8000-000000000004",
        "speaker_id": "spk-omar",
        "title": "From Monolith to CQRS",
        "abstract": (
            "A migration story: splitting write commands from read models while keeping "
            "a single Flask app and an MS SQL event store."
        ),
        "category": "architecture",
        "status": "under_review",
        "ai_assessment": {
            "status": "queued",
            "quality_score": 38,
            "summary": "Placeholder assessment seeded for local and Somee testing.",
            "queued_for_background_agent": True,
            "source": "seed",
        },
    },
]

BOOKINGS = [
    {
        "id": "c3e00000-0000-4000-8000-000000000001",
        "attendee_id": "att-noah",
        "event_id": "a1e00000-0000-4000-8000-000000000001",
        "seats": 2,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000002",
        "attendee_id": "att-lia",
        "event_id": "a1e00000-0000-4000-8000-000000000001",
        "seats": 1,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000003",
        "attendee_id": "att-yonatan",
        "event_id": "a1e00000-0000-4000-8000-000000000001",
        "seats": 2,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000004",
        "attendee_id": "att-sara",
        "event_id": "a1e00000-0000-4000-8000-000000000002",
        "seats": 2,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000005",
        "attendee_id": "att-amir",
        "event_id": "a1e00000-0000-4000-8000-000000000002",
        "seats": 1,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000006",
        "attendee_id": "att-noah",
        "event_id": "a1e00000-0000-4000-8000-000000000003",
        "seats": 1,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000007",
        "attendee_id": "att-lia",
        "event_id": "a1e00000-0000-4000-8000-000000000004",
        "seats": 3,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000008",
        "attendee_id": "att-yonatan",
        "event_id": "a1e00000-0000-4000-8000-000000000004",
        "seats": 3,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000009",
        "attendee_id": "att-sara",
        "event_id": "a1e00000-0000-4000-8000-000000000004",
        "seats": 3,
        "status": "confirmed",
    },
    {
        "id": "c3e00000-0000-4000-8000-000000000010",
        "attendee_id": "att-amir",
        "event_id": "a1e00000-0000-4000-8000-000000000004",
        "seats": 3,
        "status": "confirmed",
    },
]

ORGANIZER_IDS = [row["id"] for row in ORGANIZERS]
SPEAKER_IDS = [row["id"] for row in SPEAKERS]
ATTENDEE_IDS = [row["id"] for row in ATTENDEES]
EVENT_IDS = [row["id"] for row in EVENTS]
SUBMISSION_IDS = [row["id"] for row in SUBMISSIONS]
BOOKING_IDS = [row["id"] for row in BOOKINGS]


def _ensure_password_hash_columns() -> None:
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    dialect = db.engine.dialect.name
    for table_name in ("organizers", "speakers", "attendees"):
        if table_name not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "password_hash" in columns:
            continue
        if dialect == "sqlite":
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN password_hash VARCHAR(255)"))
        else:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD password_hash VARCHAR(255) NULL"))
    db.session.commit()


def _upsert(model, record: dict[str, Any]) -> str:
    row = db.session.get(model, record["id"])
    if row is None:
        db.session.add(model(**record))
        return "created"
    for key, value in record.items():
        if key != "id":
            setattr(row, key, value)
    return "updated"


def _upsert_account(model, record: dict[str, Any]) -> str:
    status = _upsert(model, record)
    row = db.session.get(model, record["id"])
    if row is not None and not row.password_hash:
        row.set_password(SEED_PASSWORD)
    return status


def _append_seed_event(event_name: str, payload: dict[str, Any]) -> None:
    marked = {**payload, "source": "seed"}
    for row in StoredEvent.query.filter_by(event_name=event_name).all():
        existing = row.payload or {}
        if existing.get("source") == "seed" and existing.get("id") == marked.get("id"):
            row.payload = marked
            return
    db.session.add(StoredEvent(event_name=event_name, payload=marked))


def reset_seed_data() -> None:
    """Delete seed identities and any API rows attached to them."""
    Booking.query.filter(
        db.or_(
            Booking.id.in_(BOOKING_IDS),
            Booking.event_id.in_(EVENT_IDS),
            Booking.attendee_id.in_(ATTENDEE_IDS),
        )
    ).delete(synchronize_session=False)

    TalkSubmission.query.filter(
        db.or_(
            TalkSubmission.id.in_(SUBMISSION_IDS),
            TalkSubmission.speaker_id.in_(SPEAKER_IDS),
        )
    ).delete(synchronize_session=False)

    Event.query.filter(
        db.or_(
            Event.id.in_(EVENT_IDS),
            Event.organizer_id.in_(ORGANIZER_IDS),
        )
    ).delete(synchronize_session=False)

    for row in list(StoredEvent.query.all()):
        if (row.payload or {}).get("source") == "seed":
            db.session.delete(row)

    Attendee.query.filter(Attendee.id.in_(ATTENDEE_IDS)).delete(synchronize_session=False)
    Speaker.query.filter(Speaker.id.in_(SPEAKER_IDS)).delete(synchronize_session=False)
    Organizer.query.filter(Organizer.id.in_(ORGANIZER_IDS)).delete(synchronize_session=False)
    db.session.flush()
    db.session.expire_all()
    db.session.expunge_all()


def seed_database(*, reset: bool = False) -> dict[str, int]:
    """Insert or update the sample dataset. Requires an active Flask app context."""
    if reset:
        reset_seed_data()

    _ensure_password_hash_columns()
    for record in ORGANIZERS:
        _upsert_account(Organizer, record)
    for record in SPEAKERS:
        _upsert_account(Speaker, record)
    for record in ATTENDEES:
        _upsert_account(Attendee, record)
    for record in EVENTS:
        _upsert(Event, record)
        _append_seed_event("EventCreated", record)
    for record in SUBMISSIONS:
        _upsert(TalkSubmission, record)
        _append_seed_event("TalkSubmitted", record)
    for record in BOOKINGS:
        _upsert(Booking, record)
        _append_seed_event("AttendeeRegistered", record)

    db.session.commit()
    return {
        "organizers": len(ORGANIZERS),
        "speakers": len(SPEAKERS),
        "attendees": len(ATTENDEES),
        "events": len(EVENTS),
        "talk_submissions": len(SUBMISSIONS),
        "bookings": len(BOOKINGS),
    }


def _mask_database_uri(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.password:
        netloc = parsed.netloc.replace(f":{parsed.password}", ":****", 1)
        return parsed._replace(netloc=netloc).geturl()
    if "PWD=" in uri.upper() or "pwd=" in uri:
        return "mssql+pyodbc:///?odbc_connect=****"
    return uri


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Seed Event Management sample data.")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Remove previous seed rows, then insert the sample set.",
    )
    args = parser.parse_args(argv)

    from main import create_app

    app = create_app()
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    print(f"Seeding database: {_mask_database_uri(uri)}")

    with app.app_context():
        db.create_all()
        summary = seed_database(reset=args.reset)

    print("Seed complete:")
    for table, count in summary.items():
        print(f"  {table}: {count}")
    print("\nUseful API identities:")
    print("  X-Organizer-Id: org-summit | org-meetup | org-campus")
    print("  X-Speaker-Id:   spk-maya | spk-daniel | spk-noa | spk-omar")
    print("  X-Attendee-Id:  att-noah | att-lia | att-yonatan | att-sara | att-amir")
    print("  event_id:       a1e00000-0000-4000-8000-000000000001  (AI Agents Summit)")
    print(f"  seed password:  {SEED_PASSWORD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
