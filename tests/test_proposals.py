from extensions import db
from models.stored_event import StoredEvent
from models.submission import DEFAULT_REJECTION_MESSAGE, TalkSubmission
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
    return client.post("/speaker/login", json={"user_id": user_id, "password": "SecurePass1"})


def _login_admin(client):
    return client.post("/login", json={"user_id": "admin", "password": "AdminPass!2026"})


def _submit_talk(client, **overrides):
    payload = {
        "title": "Proposal for review",
        "abstract": "A detailed summary of the talk for organizers.",
        "category": "architecture",
        "date": "2026-11-12",
        "start_time": "11:00",
        "end_time": "12:00",
        "capacity": 100,
    }
    payload.update(overrides)
    return client.post("/api/submit", json=payload)


def test_pending_proposals_list_includes_details(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()
    client.post("/logout")
    _login_admin(client)

    pending = client.get("/api/organizer/proposals")
    assert pending.status_code == 200
    match = next(item for item in pending.get_json() if item["id"] == created["id"])
    assert match["speaker_name"] == "Maya Cohen"
    assert match["title"] == "Proposal for review"
    assert match["abstract"] == "A detailed summary of the talk for organizers."
    assert match["category"] == "architecture"
    assert match["date"] == "2026-11-12"
    assert match["start_time"] == "11:00"
    assert match["end_time"] == "12:00"
    assert match["capacity"] == 100

    detail = client.get(f"/api/organizer/proposals/{created['id']}")
    assert detail.status_code == 200
    assert detail.get_json()["abstract"] == match["abstract"]


def test_approve_proposal_creates_official_event(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Approve into program").get_json()
    client.post("/logout")
    _login_admin(client)

    approved = client.post(f"/api/organizer/proposals/{created['id']}/approve")
    assert approved.status_code == 200
    body = approved.get_json()
    assert body["status"] == "approved"
    assert body["event_id"]

    pending = client.get("/api/organizer/proposals").get_json()
    assert all(item["id"] != created["id"] for item in pending)

    events = client.get("/api/organizer/events").get_json()
    match = next(item for item in events if item["id"] == body["event_id"])
    assert match["title"] == "Approve into program"
    assert match["status"] == "approved"
    assert match["available"] is True

    public = client.get("/api/attendee/approved").get_json()
    assert any(item["id"] == body["event_id"] for item in public)

    with app.app_context():
        row = db.session.get(TalkSubmission, created["id"])
        assert row.status == "approved"
        assert row.event_id == body["event_id"]


def test_reject_restore_and_delete_trash(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Needs another look").get_json()
    client.post("/logout")
    _login_admin(client)

    rejected = client.post(f"/api/organizer/proposals/{created['id']}/reject")
    assert rejected.status_code == 200
    assert rejected.get_json()["status"] == "rejected"
    assert rejected.get_json()["rejection_message"] == DEFAULT_REJECTION_MESSAGE
    assert rejected.get_json()["days_remaining"] >= 1

    pending = client.get("/api/organizer/proposals").get_json()
    assert all(item["id"] != created["id"] for item in pending)

    trash = client.get("/api/organizer/trash").get_json()
    assert any(item["id"] == created["id"] for item in trash)

    with app.app_context():
        notices = StoredEvent.query.filter_by(event_name="SpeakerNotified").all()
        assert any(
            item.payload.get("submission_id") == created["id"]
            and item.payload.get("kind") == "proposal_rejected"
            for item in notices
        )

    client.post("/logout")
    _login_speaker(client)
    mine = client.get("/api/speaker/submissions").get_json()["submissions"]
    notice = next(item for item in mine if item["id"] == created["id"])
    assert notice["status"] == "rejected"
    assert notice["display_status"] == "Not approved"
    assert notice["notification"] == DEFAULT_REJECTION_MESSAGE

    client.post("/logout")
    _login_admin(client)
    restored = client.post(f"/api/organizer/trash/{created['id']}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["status"] == "under_review"
    assert restored.get_json()["rejection_message"] is None

    pending = client.get("/api/organizer/proposals").get_json()
    assert any(item["id"] == created["id"] for item in pending)
    assert client.get("/api/organizer/trash").get_json() == []

    client.post(f"/api/organizer/proposals/{created['id']}/reject")
    deleted = client.delete(f"/api/organizer/trash/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.get_json()["id"] == created["id"]
    assert client.get("/api/organizer/trash").get_json() == []
    assert client.get(f"/api/organizer/proposals/{created['id']}").status_code == 404


def test_delete_event_removes_it_from_program(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Temporary session").get_json()
    client.post("/logout")
    _login_admin(client)
    approved = client.post(f"/api/organizer/proposals/{created['id']}/approve")
    assert approved.status_code == 200
    event_id = approved.get_json()["event_id"]

    removed = client.delete(f"/api/organizer/events/{event_id}")
    assert removed.status_code == 200
    assert removed.get_json()["id"] == event_id
    events = client.get("/api/organizer/events").get_json()
    assert all(item["id"] != event_id for item in events)
