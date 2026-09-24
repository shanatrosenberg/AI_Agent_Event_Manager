from extensions import db
from models.submission import TalkSubmission
from services.auth import admin_organizer_id


def _register_speaker(client, user_id="spk-maya", name="Maya Cohen"):
    return client.post(
        "/register",
        json={
            "user_id": user_id,
            "password": "SecurePass1",
            "role": "speaker",
            "name": name,
        },
    )


def _login_speaker(client, user_id="spk-maya"):
    return client.post(
        "/speaker/login",
        json={"user_id": user_id, "password": "SecurePass1"},
    )


def _login_admin(client):
    return client.post(
        "/login",
        json={"user_id": "admin", "password": "AdminPass!2026"},
    )


def test_speaker_dashboard_redirects_anonymous_users(client):
    response = client.get("/speaker")
    assert response.status_code == 302
    assert "/speaker/login" in response.headers["Location"]


def test_speaker_login_and_dashboard(client):
    created = _register_speaker(client)
    assert created.status_code == 201
    login = _login_speaker(client)
    assert login.status_code == 200
    assert login.get_json()["role"] == "speaker"

    response = client.get("/speaker")
    assert response.status_code == 200
    assert b"Your talks" in response.data
    assert b"Submit a talk proposal" in response.data
    assert b"Organizer requests" in response.data


def test_submit_alias_uses_session_speaker(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/submit",
        json={
            "title": "Building CQRS with Flask",
            "abstract": "A practical walkthrough of commands and queries.",
            "category": "architecture",
            "date": "2026-11-12",
            "start_time": "09:00",
            "end_time": "10:00",
            "capacity": 50,
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["speaker_id"] == "spk-maya"
    assert body["organizer_id"] == admin_organizer_id()
    assert body["display_status"] == "Reviewed by AI"
    assert body["date"] == "2026-11-12"
    assert body["start_time"] == "09:00"
    assert body["end_time"] == "10:00"
    assert body["capacity"] == 50
    assert body["hall_label"] == "50 seats"


def test_organizer_can_request_and_speaker_can_accept(client):
    _register_speaker(client)
    _login_admin(client)
    invited = client.post(
        "/api/organizer/requests",
        json={
            "speaker_id": "spk-maya",
            "topic": "RAG for abstracts",
            "details": "Show a retrieval pipeline.",
            "category": "ai",
            "date": "2026-12-01",
            "start_time": "14:00",
            "end_time": "15:00",
            "capacity": 100,
        },
    )
    assert invited.status_code == 201
    request_id = invited.get_json()["id"]
    assert invited.get_json()["status"] == "pending"
    assert invited.get_json()["date"] == "2026-12-01"
    assert invited.get_json()["capacity"] == 100

    client.post("/logout")
    _login_speaker(client)
    incoming = client.get("/api/speaker/requests")
    assert incoming.status_code == 200
    request_body = incoming.get_json()["requests"][0]
    assert request_body["topic"] == "RAG for abstracts"
    assert request_body["start_time"] == "14:00"
    assert request_body["hall_label"] == "100 seats"

    accepted = client.post(
        f"/api/speaker/requests/{request_id}/respond",
        json={"response": "accept"},
    )
    assert accepted.status_code == 200
    assert accepted.get_json()["status"] == "accepted"
    assert accepted.get_json()["submission_id"]
    event_id = accepted.get_json()["event_id"]
    assert event_id

    submissions = client.get("/api/speaker/submissions").get_json()["submissions"]
    assert any(item["title"] == "RAG for abstracts" for item in submissions)

    client.post("/logout")
    _login_admin(client)
    events = client.get("/api/organizer/events").get_json()
    assert any(item["id"] == event_id and item["status"] == "approved" for item in events)
    approved = client.get("/api/attendee/approved").get_json()
    matching = next(item for item in approved if item["id"] == event_id)
    assert matching["title"] == "RAG for abstracts"
    assert matching["date"] == "2026-12-01"
    assert matching["capacity"] == 100
    assert matching["speaker_id"] == "spk-maya"


def test_organizer_request_requires_schedule(client):
    _register_speaker(client)
    _login_admin(client)
    response = client.post(
        "/api/organizer/requests",
        json={"speaker_id": "spk-maya", "topic": "Missing slot"},
    )
    assert response.status_code == 400
    assert "date" in response.get_json()["error"]


def test_speaker_can_decline_request(client):
    _register_speaker(client)
    _login_admin(client)
    request_id = client.post(
        "/api/organizer/requests",
        json={
            "speaker_id": "spk-maya",
            "topic": "Legacy talk",
            "date": "2026-12-02",
            "start_time": "09:00",
            "end_time": "10:00",
            "capacity": 50,
        },
    ).get_json()["id"]
    client.post("/logout")
    _login_speaker(client)
    declined = client.post(
        f"/api/speaker/requests/{request_id}/respond",
        json={"response": "decline"},
    )
    assert declined.status_code == 200
    assert declined.get_json()["status"] == "declined"


def test_organizer_can_approve_submission(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = client.post(
        "/api/submit",
        json={
            "title": "Approve me",
            "abstract": "Ready for review.",
            "category": "ai",
            "date": "2026-11-12",
            "start_time": "11:00",
            "end_time": "12:00",
            "capacity": 100,
        },
    ).get_json()
    client.post("/logout")
    _login_admin(client)
    approved = client.post(f"/api/organizer/submissions/{created['id']}/approve")
    assert approved.status_code == 200
    assert approved.get_json()["status"] == "approved"
    assert approved.get_json()["display_status"] == "Approved"

    with app.app_context():
        row = db.session.get(TalkSubmission, created["id"])
        assert row.status == "approved"


def test_speaker_html_login_renders(client):
    _register_speaker(client)
    response = client.get("/speaker/login")
    assert response.status_code == 200
    assert b"Speaker sign in" in response.data
    assert b"Your profile" in response.data
    assert b"Maya Cohen" in response.data
    assert b'name="user_id"' in response.data
    assert b"<select" in response.data


def test_speaker_session_binds_identity_without_manual_id(client):
    _register_speaker(client)
    login = client.post(
        "/speaker/login",
        json={"user_id": "Maya Cohen", "password": "SecurePass1"},
    )
    assert login.status_code == 200
    assert login.get_json()["user_id"] == "spk-maya"
    assert login.get_json()["name"] == "Maya Cohen"

    me = client.get("/api/speaker/me")
    assert me.status_code == 200
    assert me.get_json()["speaker_id"] == "spk-maya"
    assert me.get_json()["speaker_name"] == "Maya Cohen"

    dashboard = client.get("/speaker")
    assert dashboard.status_code == 200
    assert b"Talks and replies are attached to this account automatically." in dashboard.data
    assert b"Maya Cohen" in dashboard.data
    with client.session_transaction() as session:
        assert session["speaker_id"] == "spk-maya"
        assert session["speaker_name"] == "Maya Cohen"

    portal = client.get("/api/speaker/portal")
    assert portal.status_code == 200
    body = portal.get_json()
    assert body["speaker_id"] == "spk-maya"
    assert body["speaker_name"] == "Maya Cohen"
    assert body["submissions"] == []
    assert body["requests"] == []


def test_logged_in_speaker_cannot_spoof_another_id(client):
    _register_speaker(client)
    _register_speaker(client, user_id="spk-other", name="Other Speaker")
    _login_speaker(client)
    response = client.post(
        "/api/submit",
        json={
            "title": "Bound to session",
            "abstract": "Identity comes from the login session.",
            "category": "ai",
            "date": "2026-11-12",
            "start_time": "13:00",
            "end_time": "14:00",
            "capacity": 300,
            "speaker_id": "spk-other",
        },
    )
    assert response.status_code == 201
    assert response.get_json()["speaker_id"] == "spk-maya"
