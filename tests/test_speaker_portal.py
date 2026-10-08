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
    assert b'id="kpi-bar"' in response.data
    assert b'id="kpi-events"' in response.data
    assert b'id="kpi-submissions"' in response.data
    assert b'id="kpi-requests"' in response.data
    assert b'id="kpi-requests-pulse"' in response.data
    assert b"Confirmed Events" in response.data
    assert b"Pending Submissions" in response.data
    assert b"Incoming Organizer Requests" in response.data
    assert b"Submit a talk proposal" in response.data
    assert b"My Confirmed Events" in response.data
    assert b"Your Submissions" in response.data
    assert b"Rejected Proposals" in response.data
    assert b'id="submission-filters"' in response.data
    assert b'id="rejected-submissions-block"' in response.data
    assert b'id="rejected-body"' in response.data
    assert b"Organizer Requests" in response.data
    assert b'id="speaker-tabs"' in response.data
    assert b'id="panel-events"' in response.data
    assert b'id="events-table-wrap"' in response.data
    assert b'id="events-body"' in response.data
    assert b'id="events-cards"' in response.data
    assert b">Event</th>" in response.data
    assert b">Speaker</th>" in response.data
    assert b">Date</th>" in response.data
    assert b">Time</th>" in response.data
    assert b">Hall</th>" in response.data
    assert b">Capacity</th>" in response.data
    assert b">Status</th>" in response.data
    assert b'id="panel-submissions"' in response.data
    assert b'id="submissions-table-wrap"' in response.data
    assert b'id="submissions-body"' in response.data
    assert b'id="submissions-cards"' in response.data
    assert b">Talk Title</th>" in response.data
    assert b">Topic</th>" in response.data
    assert b">Hall</th>" in response.data
    assert b">Status</th>" in response.data
    assert b'id="panel-requests"' in response.data
    assert b'id="requests-table-wrap"' in response.data
    assert b'id="requests-body"' in response.data
    assert b'id="requests-cards"' in response.data
    html = response.get_data(as_text=True)
    assert html.index('data-tab="events"') < html.index('data-tab="submissions"') < html.index('data-tab="requests"')
    assert b'id="open-proposal-modal"' in response.data
    assert html.index('id="panel-submissions"') < html.index('id="open-proposal-modal"') < html.index('id="panel-requests"')
    assert b'id="proposal-modal"' in response.data
    assert b'id="close-proposal-modal"' in response.data
    assert b'id="cancel-proposal-modal"' in response.data
    assert 'id="proposal-modal" class="fixed inset-0 z-50 hidden' in response.get_data(as_text=True)
    assert b'id="submit-talk-form"' in response.data
    assert b'id="title"' in response.data
    assert b'id="abstract"' in response.data
    assert b'id="enhance-abstract"' in response.data
    assert b"Enhance with AI" in response.data
    assert b'id="enhance-abstract-spinner"' in response.data
    assert b'id="category"' in response.data
    assert b'value="other"' in response.data
    assert b'id="custom-topic-input"' in response.data
    assert b'name="custom_topic"' in response.data
    assert b'id="date"' in response.data
    assert b'id="start_time"' in response.data
    assert b'id="end_time"' in response.data
    assert b'id="capacity"' in response.data
    assert b"Submit Proposal" in response.data


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


def test_submit_talk_saves_custom_topic(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/submit",
        json={
            "title": "Observability for event systems",
            "abstract": "A practical walkthrough of tracing talk submissions.",
            "category": "other",
            "custom_topic": "Observability",
            "date": "2026-11-18",
            "start_time": "11:00",
            "end_time": "12:00",
            "capacity": 100,
        },
    )
    assert response.status_code == 201
    body = response.get_json()
    assert body["category"] == "Observability"
    stored = TalkSubmission.query.filter_by(id=body["id"]).one()
    assert stored.category == "Observability"


def test_submit_talk_requires_custom_topic_when_other(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/submit",
        json={
            "title": "Observability for event systems",
            "abstract": "A practical walkthrough of tracing talk submissions.",
            "category": "other",
            "custom_topic": "",
            "date": "2026-11-18",
            "start_time": "11:00",
            "end_time": "12:00",
            "capacity": 100,
        },
    )
    assert response.status_code == 400
    assert "custom topic" in response.get_json()["error"].lower()


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
    assert invited.get_json()["confirmation"] == "awaiting"
    assert invited.get_json()["display_status"] == "Awaiting Speaker Confirmation"
    assert invited.get_json()["date"] == "2026-12-01"
    assert invited.get_json()["capacity"] == 100
    awaiting = client.get("/api/organizer/requests?confirmation=awaiting").get_json()
    assert any(item["id"] == request_id and item["confirmation"] == "awaiting" for item in awaiting)
    assert all(item["id"] != request_id for item in client.get("/api/organizer/requests?confirmation=confirmed").get_json())

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
    portal = client.get("/api/speaker/portal").get_json()
    assert all(item["id"] != request_id for item in portal["requests"])
    assert any(item["id"] == event_id and item["title"] == "RAG for abstracts" for item in portal["events"])
    assert all(item["title"] != "RAG for abstracts" for item in portal["submissions"])
    assert portal["events"][0]["abstract"]
    events = client.get("/api/speaker/events").get_json()["events"]
    assert [item["id"] for item in events] == [event_id]

    client.post("/logout")
    _login_admin(client)
    confirmed = client.get("/api/organizer/requests?confirmation=confirmed").get_json()
    match = next(item for item in confirmed if item["id"] == request_id)
    assert match["confirmation"] == "confirmed"
    assert match["display_status"] == "Speaker Confirmed"
    assert match["event_id"] == event_id
    assert all(item["id"] != request_id for item in client.get("/api/organizer/requests?confirmation=awaiting").get_json())
    events = client.get("/api/organizer/events").get_json()
    assert any(item["id"] == event_id and item["status"] == "approved" for item in events)
    approved = client.get("/api/attendee/approved").get_json()
    matching = next(item for item in approved if item["id"] == event_id)
    assert matching["title"] == "RAG for abstracts"
    assert matching["date"] == "2026-12-01"
    assert matching["capacity"] == 100
    assert matching["speaker_id"] == "spk-maya"


def test_speaker_confirmed_events_sort_and_pending_requests_only(client):
    _register_speaker(client)
    _login_admin(client)
    later = client.post(
        "/api/organizer/requests",
        json={
            "speaker_id": "spk-maya",
            "topic": "Later lecture",
            "details": "A later session summary.",
            "date": "2026-12-20",
            "start_time": "16:00",
            "end_time": "17:00",
            "capacity": 50,
        },
    ).get_json()
    earlier = client.post(
        "/api/organizer/requests",
        json={
            "speaker_id": "spk-maya",
            "topic": "Earlier lecture",
            "details": "The closest upcoming session.",
            "date": "2026-11-05",
            "start_time": "09:00",
            "end_time": "10:00",
            "capacity": 100,
        },
    ).get_json()
    leftover = client.post(
        "/api/organizer/requests",
        json={
            "speaker_id": "spk-maya",
            "topic": "Still waiting",
            "details": "Not answered yet.",
            "date": "2026-12-02",
            "start_time": "11:00",
            "end_time": "12:00",
            "capacity": 300,
        },
    ).get_json()
    client.post("/logout")
    _login_speaker(client)
    pending = client.get("/api/speaker/portal").get_json()
    assert {item["id"] for item in pending["requests"]} == {later["id"], earlier["id"], leftover["id"]}
    assert pending["events"] == []

    client.post(f"/api/speaker/requests/{later['id']}/respond", json={"response": "accept"})
    client.post(f"/api/speaker/requests/{earlier['id']}/respond", json={"response": "accept"})
    portal = client.get("/api/speaker/portal").get_json()
    assert [item["title"] for item in portal["events"]] == ["Earlier lecture", "Later lecture"]
    assert [item["date"] for item in portal["events"]] == ["2026-11-05", "2026-12-20"]
    assert [item["id"] for item in portal["requests"]] == [leftover["id"]]
    assert all(item["status"] == "pending" for item in portal["requests"])
    assert portal["events"][0]["hall_label"] == "100 seats"
    assert "closest upcoming session" in portal["events"][0]["abstract"]


def test_organizer_requests_reject_unknown_confirmation_filter(client):
    _login_admin(client)
    response = client.get("/api/organizer/requests?confirmation=later")
    assert response.status_code == 400
    assert "awaiting or confirmed" in response.get_json()["error"]


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
    assert approved.get_json()["event_id"]
    assert approved.get_json()["event"]["id"] == approved.get_json()["event_id"]

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
    assert b'data-speaker-id="spk-maya"' in dashboard.data
    assert b'data-speaker-name="Maya Cohen"' in dashboard.data
    assert b"Maya Cohen" in dashboard.data
    with client.session_transaction() as session:
        assert session["speaker_id"] == "spk-maya"
        assert session["speaker_name"] == "Maya Cohen"

    portal = client.get("/api/speaker/portal")
    assert portal.status_code == 200
    body = portal.get_json()
    assert body["speaker_id"] == "spk-maya"
    assert body["speaker_name"] == "Maya Cohen"
    assert body["events"] == []
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


def test_enhance_abstract_requires_speaker_login(client):
    response = client.post("/api/enhance-abstract", json={"abstract": "A draft talk about CQRS."})
    assert response.status_code == 401


def test_enhance_abstract_requires_draft_text(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post("/api/enhance-abstract", json={"abstract": "Too short"})
    assert response.status_code == 400


def test_enhance_abstract_accepts_dashboard_session_keys(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    _register_speaker(client)
    with client.session_transaction() as stored:
        stored["user_id"] = "spk-maya"
        stored["role"] = "speaker"
        stored["name"] = "Maya Cohen"
        stored["speaker_id"] = "spk-maya"
        stored["speaker_name"] = "Maya Cohen"
    response = client.post(
        "/api/speaker/enhance-abstract",
        json={"abstract": "A practical walkthrough of commands and queries."},
    )
    assert response.status_code == 503
    assert "Hugging Face" in response.get_json()["error"]


def test_enhance_abstract_requires_huggingface_token(client, monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_API_KEY", raising=False)
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/enhance-abstract",
        json={"abstract": "A practical walkthrough of commands and queries."},
    )
    assert response.status_code == 503


def test_enhance_abstract_uses_flan_t5_serverless_api(client, app, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    app.config["HUGGINGFACE_API_KEY"] = "hf-test-token"
    captured = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return [{"generated_text": "A polished conference abstract on CQRS for event organizers."}]

    def fake_post(url, headers=None, json=None, timeout=0):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        return FakeResponse()

    monkeypatch.setattr("controllers.speaker.requests.post", fake_post)
    response = client.post(
        "/api/enhance-abstract",
        json={
            "title": "Building CQRS with Flask",
            "category": "architecture",
            "abstract": "A practical walkthrough of commands and queries.",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["abstract"] == "A polished conference abstract on CQRS for event organizers."
    assert body["enhanced_abstract"] == body["abstract"]
    assert body["model"] == "google/flan-t5-large"
    assert captured["url"] == "https://api-inference.huggingface.co/models/google/flan-t5-large"
    assert captured["headers"]["Authorization"] == "Bearer hf-test-token"
    assert captured["json"]["parameters"]["max_length"] == 200
    assert "Rewrite this conference talk abstract" in captured["json"]["inputs"]
    assert "A practical walkthrough" in captured["json"]["inputs"]


def test_enhance_abstract_returns_huggingface_exception_details(client, app, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)
    monkeypatch.setenv("HF_TOKEN", "hf-test-token")
    app.config["HUGGINGFACE_API_KEY"] = "hf-test-token"

    class FakeResponse:
        status_code = 403

        def json(self):
            return {"error": "StopIteration from inference provider mapping"}

    monkeypatch.setattr(
        "controllers.speaker.requests.post",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    response = client.post(
        "/api/enhance-abstract",
        json={"abstract": "A practical walkthrough of commands and queries."},
    )
    assert response.status_code == 500
    assert "StopIteration" in response.get_json()["error"]
