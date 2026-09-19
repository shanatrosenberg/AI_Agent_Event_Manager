from extensions import db
from models.attendee import Attendee
from models.booking import Booking
from models.event import Event
from models.organizer import Organizer
from models.speaker import Speaker
from models.stored_event import StoredEvent
from models.submission import TalkSubmission
from scripts.seed import (
    ATTENDEES,
    BOOKINGS,
    EVENTS,
    ORGANIZERS,
    SPEAKERS,
    SUBMISSIONS,
    seed_database,
)


def test_seed_populates_core_tables(app):
    with app.app_context():
        summary = seed_database()

        assert summary == {
            "organizers": len(ORGANIZERS),
            "speakers": len(SPEAKERS),
            "attendees": len(ATTENDEES),
            "events": len(EVENTS),
            "talk_submissions": len(SUBMISSIONS),
            "bookings": len(BOOKINGS),
        }
        assert Organizer.query.count() == len(ORGANIZERS)
        assert Speaker.query.count() == len(SPEAKERS)
        assert Attendee.query.count() == len(ATTENDEES)
        assert Event.query.count() == len(EVENTS)
        assert TalkSubmission.query.count() == len(SUBMISSIONS)
        assert Booking.query.count() == len(BOOKINGS)
        assert StoredEvent.query.count() >= len(EVENTS)

        summit = db.session.get(Organizer, "org-summit")
        assert summit is not None
        assert summit.name == "Tech Summit Israel"

        event = db.session.get(Event, "a1e00000-0000-4000-8000-000000000001")
        assert event is not None
        assert event.organizer_id == "org-summit"
        assert event.remaining_seats == event.capacity - event.seats_booked
        assert event.status == "active"

        sold_out = db.session.get(Event, "a1e00000-0000-4000-8000-000000000004")
        assert sold_out is not None
        assert sold_out.remaining_seats == 0

        cancelled = db.session.get(Event, "a1e00000-0000-4000-8000-000000000005")
        assert cancelled is not None
        assert cancelled.status == "cancelled"


def test_seed_keeps_booking_totals_in_sync(app):
    with app.app_context():
        seed_database()
        for event in Event.query.all():
            booked = sum(
                booking.seats
                for booking in Booking.query.filter_by(event_id=event.id, status="confirmed")
            )
            assert event.seats_booked == booked


def test_seed_is_idempotent(app):
    with app.app_context():
        seed_database()
        seed_database()

        assert Organizer.query.count() == len(ORGANIZERS)
        assert Speaker.query.count() == len(SPEAKERS)
        assert Attendee.query.count() == len(ATTENDEES)
        assert Event.query.count() == len(EVENTS)
        assert TalkSubmission.query.count() == len(SUBMISSIONS)
        assert Booking.query.count() == len(BOOKINGS)
        assert db.session.get(Organizer, "org-summit").name == "Tech Summit Israel"


def test_seed_reset_replaces_existing_seed_rows(app):
    with app.app_context():
        seed_database()
        organizer = db.session.get(Organizer, "org-summit")
        organizer.name = "Changed Name"
        db.session.get(Event, "a1e00000-0000-4000-8000-000000000001").title = "Changed Title"

        seed_database(reset=True)

        assert db.session.get(Organizer, "org-summit").name == "Tech Summit Israel"
        assert db.session.get(Event, "a1e00000-0000-4000-8000-000000000001").title == (
            "AI Agents Summit 2026"
        )
        assert Event.query.count() == len(EVENTS)
