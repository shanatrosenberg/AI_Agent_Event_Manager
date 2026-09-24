from extensions import db
from models.organizer import Organizer
from models.stored_event import StoredEvent
from services.auth import (
    INVALID_CREDENTIALS,
    admin_organizer_id,
    admin_organizer_password,
    admin_organizer_username,
    read_auth_token,
)


def _login_admin(client, **overrides):
    payload = {
        "user_id": admin_organizer_username(),
        "password": admin_organizer_password(),
    }
    payload.update(overrides)
    return client.post("/login", json=payload)


def _register_speaker(client, **overrides):
    payload = {
        "user_id": "spk-1",
        "password": "SecurePass1",
        "role": "speaker",
        "name": "Speaker One",
    }
    payload.update(overrides)
    return client.post("/register", json=payload)


def test_admin_login_sets_session(client):
    response = _login_admin(client)
    assert response.status_code == 200
    body = response.get_json()
    assert body["user_id"] == admin_organizer_id()
    assert body["role"] == "organizer"
    assert "password" not in body
    assert "token" in body
    with client.session_transaction() as session:
        assert session["user_id"] == admin_organizer_id()
        assert session["role"] == "organizer"


def test_admin_login_accepts_short_username(client):
    response = _login_admin(client, user_id="admin")
    assert response.status_code == 200
    assert response.get_json()["user_id"] == admin_organizer_id()


def test_login_rejects_bad_password(client):
    response = _login_admin(client, password="wrong-password")
    assert response.status_code == 401
    assert response.get_json()["error"] == INVALID_CREDENTIALS
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_login_rejects_unknown_user_with_same_message(client):
    response = client.post(
        "/login",
        json={"user_id": "missing", "password": "SecurePass1"},
    )
    assert response.status_code == 401
    assert response.get_json()["error"] == INVALID_CREDENTIALS


def test_password_hash_is_not_exposed(app):
    with app.app_context():
        organizer = db.session.get(Organizer, admin_organizer_id())
        assert organizer is not None
        assert organizer.password_hash
        assert organizer.password_hash != admin_organizer_password()
        assert "password" not in organizer.to_dict()
        assert "password_hash" not in organizer.to_dict()


def test_login_records_domain_event(client, app):
    _login_admin(client)
    with app.app_context():
        events = StoredEvent.query.filter_by(event_name="UserLoggedIn").all()
        assert len(events) == 1
        assert events[0].payload["user_id"] == admin_organizer_id()
        assert "password" not in events[0].payload


def test_login_token_round_trip(client, app):
    token = _login_admin(client).get_json()["token"]
    with app.app_context():
        payload = read_auth_token(token)
    assert payload == {"user_id": admin_organizer_id(), "role": "organizer"}


def test_register_rejects_organizer_role(client):
    response = client.post(
        "/register",
        json={
            "user_id": "org-other",
            "password": "SecurePass1",
            "role": "organizer",
            "name": "Other Org",
        },
    )
    assert response.status_code == 403
    assert "cannot be self-registered" in response.get_json()["error"]


def test_organizer_dashboard_redirects_anonymous_users(client):
    response = client.get("/organizer")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_organizer_dashboard_allows_signed_in_admin(client):
    _login_admin(client)
    response = client.get("/organizer")
    assert response.status_code == 200
    assert b"Manage your program" in response.data
    assert admin_organizer_id().encode() in response.data
    assert admin_organizer_username().encode() in response.data
    assert b'id="invite_speaker_id"' in response.data
    assert b'id="create-event-form"' not in response.data
    assert b"Create Event" not in response.data
    assert b"Request Speaker" in response.data
    assert b"Pending Proposals" in response.data
    assert b"Manage Proposals" in response.data
    assert b"My Events" in response.data
    assert b"Disapproved / Trash Events" in response.data
    assert b'id="organizer-tabs"' in response.data
    assert b'id="panel-create"' not in response.data
    assert b'id="panel-request"' in response.data
    assert b'id="panel-proposals"' in response.data
    assert b'id="panel-events"' in response.data
    assert b'id="panel-trash"' in response.data


def test_organizer_dashboard_rejects_other_roles(client):
    _register_speaker(client)
    with client.session_transaction() as session:
        session["user_id"] = "spk-1"
        session["role"] = "speaker"
        session["name"] = "Speaker One"
    response = client.get("/organizer")
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]


def test_html_login_renders_admin_form(client):
    response = client.get("/login")
    assert response.status_code == 200
    assert b"Admin sign in" in response.data
    assert b'name="password"' in response.data
    assert b'name="user_id"' in response.data


def test_signed_in_admin_events_use_admin_id(client, speaker_headers, event_payload):
    submitted = client.post(
        "/api/speaker/submit",
        json={
            "title": event_payload["title"],
            "abstract": event_payload["description"],
            "category": "general",
            "date": event_payload["date"],
            "start_time": event_payload["start_time"],
            "end_time": event_payload["end_time"],
            "capacity": event_payload["capacity"],
        },
        headers=speaker_headers,
    )
    assert submitted.status_code == 201

    _login_admin(client)
    approved = client.post(
        f"/api/organizer/proposals/{submitted.get_json()['id']}/approve",
        headers={"X-Organizer-Id": "spoofed-org"},
    )
    assert approved.status_code == 200
    event_id = approved.get_json()["event_id"]

    listed = client.get("/api/organizer/events")
    assert listed.status_code == 200
    events = listed.get_json()
    assert len(events) == 1
    assert events[0]["id"] == event_id
    assert events[0]["organizer_id"] == admin_organizer_id()
