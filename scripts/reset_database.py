"""Wipe all rows and recreate an empty application schema.

Does not insert demo events, speakers, attendees, or bookings.
The single organizer admin account is restored so the app can still sign in.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import inspect

from extensions import db
from main import create_app
from services.auth import (
    ensure_admin_organizer,
    ensure_event_schedule_columns,
    ensure_event_speaker_column,
    ensure_password_hash_columns,
    ensure_talk_portal_schema,
)
from cqrs.store import ensure_event_store_schema
from services.seating import ensure_booking_seat_schema
from services.waitlist import ensure_waitlist_schema


def reset_database() -> dict[str, int]:
    removed: dict[str, int] = {}
    inspector = inspect(db.engine)
    existing = set(inspector.get_table_names())
    for table in reversed(db.metadata.sorted_tables):
        if table.name not in existing:
            continue
        count = db.session.execute(table.delete()).rowcount or 0
        removed[table.name] = int(count)
    db.session.commit()
    db.create_all()
    ensure_password_hash_columns()
    ensure_event_speaker_column()
    ensure_event_schedule_columns()
    ensure_talk_portal_schema()
    ensure_event_store_schema()
    ensure_booking_seat_schema()
    ensure_waitlist_schema()
    ensure_admin_organizer()
    db.session.commit()
    return removed


def main() -> None:
    app = create_app({"ASSESSMENT_AGENT_AUTOSTART": False})
    with app.app_context():
        removed = reset_database()
        print("Cleared tables:")
        for name, count in removed.items():
            print(f"  {name}: {count} row(s)")
        from models.event import Event

        remaining_events = Event.query.count()
        print(f"Events remaining: {remaining_events}")
        print("Schema kept: empty events (title, description, date, start_time, end_time) plus required app tables.")


if __name__ == "__main__":
    main()
