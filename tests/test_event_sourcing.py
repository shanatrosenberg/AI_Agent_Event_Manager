from models.stored_event import StoredEvent
from cqrs.events import TALK_APPROVED, TALK_INNOVATION_REVIEWED, TALK_PROPOSED, TALK_REJECTED
from cqrs.projections import project_talk_state
from cqrs.store import EventStore


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
        "title": "Event sourced proposal",
        "abstract": "A talk that should appear in the immutable event stream.",
        "category": "architecture",
        "date": "2026-11-12",
        "start_time": "11:00",
        "end_time": "12:00",
        "capacity": 100,
    }
    payload.update(overrides)
    return client.post("/api/submit", json=payload)


def test_submit_emits_proposed_and_reviewed_events(client, app):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client).get_json()

    with app.app_context():
        names = [row.event_name for row in StoredEvent.query.order_by(StoredEvent.id.asc()).all()]
        assert TALK_PROPOSED in names
        assert TALK_INNOVATION_REVIEWED in names
        proposed = StoredEvent.query.filter_by(event_name=TALK_PROPOSED).first()
        assert proposed.aggregate_id == created["id"]
        assert proposed.aggregate_type == "talk"
        assert proposed.occurred_at is not None
        assert proposed.payload["title"] == "Event sourced proposal"


def test_approve_and_reject_append_lifecycle_events(client, app):
    _register_speaker(client)
    _login_speaker(client)
    first = _submit_talk(client, title="Approve this talk").get_json()
    second = _submit_talk(
        client,
        title="Reject this talk",
        date="2026-11-13",
        start_time="13:00",
        end_time="14:00",
    ).get_json()
    client.post("/logout")
    _login_admin(client)

    approved = client.post(f"/api/organizer/proposals/{first['id']}/approve")
    rejected = client.post(f"/api/organizer/proposals/{second['id']}/reject")
    assert approved.status_code == 200
    assert rejected.status_code == 200

    with app.app_context():
        names = [row.event_name for row in StoredEvent.query.all()]
        assert TALK_APPROVED in names
        assert TALK_REJECTED in names
        store = EventStore()
        projected = {item["id"]: item for item in store.project_talks()}
        assert projected[first["id"]]["status"] == "approved"
        assert projected[first["id"]]["last_event"] == TALK_APPROVED
        assert projected[second["id"]]["status"] == "rejected"
        assert projected[second["id"]]["last_event"] == TALK_REJECTED


def test_projection_rebuilds_talk_state_from_stream():
    events = [
        {"event_name": "TalkSubmitted", "payload": {"id": "t1", "title": "Legacy name", "status": "pending_assessment"}},
        {"event_name": "TalkAssessedByAgent", "payload": {"id": "t1", "status": "under_review", "innovation_score": 88, "innovation_badge": "High Innovation"}},
        {"event_name": TALK_APPROVED, "payload": {"id": "t1", "status": "approved", "event_id": "evt-1"}},
    ]
    snapshot = project_talk_state(events)["t1"]
    assert snapshot["title"] == "Legacy name"
    assert snapshot["status"] == "approved"
    assert snapshot["innovation_score"] == 88
    assert snapshot["event_id"] == "evt-1"
    assert snapshot["version"] == 3
    assert snapshot["last_event"] == TALK_APPROVED


def test_organizer_event_log_lists_chronological_audit_trail(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit_talk(client, title="Audit trail talk").get_json()
    client.post("/logout")
    _login_admin(client)
    client.post(f"/api/organizer/proposals/{created['id']}/approve")

    log = client.get("/api/organizer/event-log")
    assert log.status_code == 200
    rows = log.get_json()
    names = [row["canonical_name"] for row in rows]
    assert TALK_PROPOSED in names
    assert TALK_INNOVATION_REVIEWED in names
    assert TALK_APPROVED in names
    assert all("occurred_at" in row for row in rows)
    assert all("label" in row and "summary" in row for row in rows)
    talk_rows = [row for row in rows if row.get("aggregate_id") == created["id"]]
    assert talk_rows
    assert talk_rows[0]["id"] >= talk_rows[-1]["id"]

    filtered = client.get("/api/organizer/event-log?event_name=TalkApproved")
    assert filtered.status_code == 200
    assert {row["canonical_name"] for row in filtered.get_json()} == {TALK_APPROVED}

    projected = client.get(f"/api/organizer/projections/talks?talk_id={created['id']}")
    assert projected.status_code == 200
    body = projected.get_json()
    assert len(body) == 1
    assert body[0]["id"] == created["id"]
    assert body[0]["status"] == "approved"
    assert body[0]["title"] == "Audit trail talk"
