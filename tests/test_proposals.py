from datetime import timedelta

from extensions import db
from models.stored_event import StoredEvent
from models.submission import DEFAULT_REJECTION_MESSAGE, TalkSubmission, utc_now
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
    assert body["display_status"] == "Approved"
    assert body["event_id"]
    assert body["event"]["id"] == body["event_id"]
    assert body["event"]["title"] == "Approve into program"
    assert body["event"]["status"] == "approved"

    pending = client.get("/api/organizer/proposals").get_json()
    assert all(item["id"] != created["id"] for item in pending)
    events = client.get("/api/organizer/events").get_json()
    match = next(item for item in events if item["id"] == body["event_id"])
    assert match["title"] == "Approve into program"
    assert match["status"] == "approved"
    public = client.get("/api/attendee/approved").get_json()
    assert any(item["id"] == body["event_id"] for item in public)
    confirmed_inbox = client.get("/api/organizer/requests?confirmation=confirmed").get_json()
    assert any(
        item["id"] == created["id"] and item["kind"] == "proposal" and item["confirmation"] == "confirmed"
        for item in confirmed_inbox
    )

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
    assert rejected.get_json()["days_remaining"] == 7
    assert rejected.get_json()["retention_days"] == 7

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
    declined = next(item for item in mine if item["id"] == created["id"])
    assert declined["status"] == "rejected"
    assert declined["display_status"] == "Rejected"
    portal = client.get("/api/speaker/portal").get_json()
    portal_declined = next(item for item in portal["submissions"] if item["id"] == created["id"])
    assert portal_declined["status"] == "rejected"
    assert portal_declined["display_status"] == "Rejected"

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


def test_trash_counts_down_and_purges_after_seven_days(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Countdown talk").get_json()
    client.post("/logout")
    _login_admin(client)
    rejected = client.post(f"/api/organizer/proposals/{created['id']}/reject")
    assert rejected.get_json()["days_remaining"] == 7

    with app.app_context():
        row = db.session.get(TalkSubmission, created["id"])
        row.rejected_at = utc_now() - timedelta(days=1)
        db.session.commit()
    trash = client.get("/api/organizer/trash").get_json()
    item = next(entry for entry in trash if entry["id"] == created["id"])
    assert item["days_remaining"] == 6

    with app.app_context():
        row = db.session.get(TalkSubmission, created["id"])
        row.rejected_at = utc_now() - timedelta(days=7)
        db.session.commit()
    assert client.get("/api/organizer/trash").get_json() == []
    assert client.get(f"/api/organizer/proposals/{created['id']}").status_code == 404


def test_rejected_proposal_appears_on_speaker_dashboard(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Speaker restore").get_json()
    client.post("/logout")
    _login_admin(client)
    client.post(f"/api/organizer/proposals/{created['id']}/reject")
    client.post("/logout")
    _login_speaker(client)
    restored = client.post(f"/api/speaker/submissions/{created['id']}/restore")
    assert restored.status_code == 403
    mine = client.get("/api/speaker/submissions").get_json()["submissions"]
    match = next(item for item in mine if item["id"] == created["id"])
    assert match["status"] == "rejected"
    assert match["display_status"] == "Rejected"
    assert match["title"] == "Speaker restore"
    assert match["category"] == "architecture"
    assert match["date"] == "2026-11-12"
    portal = client.get("/api/speaker/portal").get_json()
    visible = next(item for item in portal["submissions"] if item["id"] == created["id"])
    assert visible["status"] == "rejected"
    assert visible["display_status"] == "Rejected"


def test_reject_event_moves_it_to_trash_and_can_restore(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Official session").get_json()
    client.post("/logout")
    _login_admin(client)
    approved = client.post(f"/api/organizer/proposals/{created['id']}/approve")
    assert approved.status_code == 200
    event_id = approved.get_json()["event_id"]

    rejected = client.post(f"/api/organizer/events/{event_id}/reject")
    assert rejected.status_code == 200
    assert rejected.get_json()["status"] == "rejected"
    assert rejected.get_json()["event_id"] == event_id
    assert rejected.get_json()["restores_to"] == "events"

    events = client.get("/api/organizer/events").get_json()
    assert all(item["id"] != event_id for item in events)
    pending = client.get("/api/organizer/proposals").get_json()
    assert all(item["id"] != created["id"] for item in pending)
    public = client.get("/api/attendee/approved").get_json()
    assert all(item["id"] != event_id for item in public)

    trash = client.get("/api/organizer/trash").get_json()
    assert any(item["id"] == created["id"] and item["event_id"] == event_id for item in trash)

    restored = client.post(f"/api/organizer/trash/{created['id']}/restore")
    assert restored.status_code == 200
    assert restored.get_json()["status"] == "approved"
    assert any(item["id"] == event_id for item in client.get("/api/organizer/events").get_json())
    assert client.get("/api/organizer/trash").get_json() == []


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
