import pytest

from extensions import db
from main import create_app
from services.auth import admin_organizer_id


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "test-secret-key",
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with application.app_context():
        db.create_all()
        from services.auth import ensure_admin_organizer

        ensure_admin_organizer()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def organizer_id():
    return "org-1"


@pytest.fixture
def speaker_id():
    return "spk-1"


@pytest.fixture
def attendee_id():
    return "att-1"


@pytest.fixture
def organizer_headers(organizer_id):
    return {"X-Organizer-Id": organizer_id}


@pytest.fixture
def speaker_headers(speaker_id):
    return {"X-Speaker-Id": speaker_id}


@pytest.fixture
def attendee_headers(attendee_id):
    return {"X-Attendee-Id": attendee_id}


@pytest.fixture
def event_payload():
    return {
        "title": "AI Summit",
        "description": "Talks on autonomous agents and event systems",
        "date": "2026-10-01",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 50,
    }


@pytest.fixture
def talk_payload():
    return {
        "title": "Building CQRS with Flask",
        "abstract": "A practical walkthrough of commands, queries, and event sourcing.",
        "category": "architecture",
        "date": "2026-11-12",
        "start_time": "09:00",
        "end_time": "10:00",
        "capacity": 50,
    }


def approve_talk_event(client, speaker_headers, event_payload, **overrides):
    talk = {
        "title": event_payload["title"],
        "abstract": event_payload.get("description") or event_payload.get("abstract") or "Talk summary",
        "category": event_payload.get("category") or "general",
        "date": event_payload["date"],
        "start_time": event_payload["start_time"],
        "end_time": event_payload["end_time"],
        "capacity": event_payload["capacity"],
    }
    talk.update(overrides)
    submitted = client.post("/api/speaker/submit", json=talk, headers=speaker_headers)
    assert submitted.status_code == 201, submitted.get_json()
    approved = client.post(f"/api/organizer/proposals/{submitted.get_json()['id']}/approve")
    assert approved.status_code == 200, approved.get_json()
    assert approved.get_json()["status"] == "approved"
    event_id = approved.get_json()["event_id"]
    assert event_id
    events = client.get(
        "/api/organizer/events",
        headers={"X-Organizer-Id": admin_organizer_id()},
    )
    assert events.status_code == 200
    return next(item for item in events.get_json() if item["id"] == event_id)


@pytest.fixture
def created_event(client, speaker_headers, event_payload):
    return approve_talk_event(client, speaker_headers, event_payload)
