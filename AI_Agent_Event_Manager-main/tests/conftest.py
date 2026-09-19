import os

# Keep test collection off the Somee SQL Server driver.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import pytest

from extensions import db
from main import create_app


@pytest.fixture
def app():
    application = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        }
    )
    with application.app_context():
        db.create_all()
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
        "capacity": 50,
    }


@pytest.fixture
def talk_payload():
    return {
        "title": "Building CQRS with Flask",
        "abstract": "A practical walkthrough of commands, queries, and event sourcing.",
        "category": "architecture",
    }


@pytest.fixture
def created_event(client, organizer_headers, event_payload):
    response = client.post(
        "/api/organizer/events",
        json=event_payload,
        headers=organizer_headers,
    )
    assert response.status_code == 201
    return response.get_json()
