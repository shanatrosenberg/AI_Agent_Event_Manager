import json

from uuid import uuid4

from extensions import db
from models.chat_message import ChatMessage
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
    assert b"AI Innovation Ideas Hub" in response.data
    assert b'id="panel-ideas"' in response.data
    assert b'id="ideas-grid"' in response.data
    assert b'id="ideas-search-form"' in response.data
    assert b'id="ideas-query"' in response.data
    assert b'id="refresh-ideas"' in response.data
    assert b'id="speaker-tabs"' in response.data
    assert b'id="panel-events"' in response.data
    assert b'id="events-table-wrap"' in response.data
    assert b'id="events-body"' in response.data
    assert b'id="events-cards"' in response.data
    assert b"My Confirmed Events" in response.data
    assert b">Event</th>" in response.data
    assert b">Speaker</th>" in response.data
    assert b">Date</th>" in response.data
    assert b">Time</th>" in response.data
    assert b">Hall</th>" in response.data
    assert b"Conference Room (50 seats)" in response.data
    assert b"Grand Hall (100 seats)" in response.data
    assert b"Main Auditorium (300 seats)" in response.data
    assert b">Open/Sold Seats</th>" in response.data
    assert b">Status</th>" in response.data
    assert b"More Details" in response.data
    assert b"Cancel Event" in response.data
    assert b"Lecture summary" in response.data
    assert b"Hall specifications" not in response.data
    assert b"Tickets already purchased" not in response.data
    assert b'id="open-speaker-chat"' in response.data
    assert b'id="chat-unread-badge"' in response.data
    assert b"-right-1 -top-1" in response.data
    assert b"bg-emerald-500" in response.data
    assert b"paintChatBadge" in response.data
    assert b'id="speaker-chat-sidebar"' in response.data
    assert b'id="chat-email-view"' in response.data
    assert b'id="chat-reply-form"' in response.data
    assert b'id="chat-reply-input"' in response.data
    assert b'id="chat-alert-popup"' in response.data
    assert b'id="speaker-messages"' in response.data
    assert b"/api/speaker/events/" in response.data
    assert b'id="event-detail-modal"' in response.data
    assert 'id="event-detail-modal" class="fixed inset-0 z-50 hidden' in response.get_data(as_text=True)
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
    assert html.index('data-tab="events"') < html.index('data-tab="submissions"') < html.index('data-tab="ideas"') < html.index('data-tab="requests"')
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
    assert b"AbortController" in response.data
    assert b"10000" in response.data
    assert b'id="category"' in response.data
    assert b'value="other"' in response.data
    assert b'id="custom-topic-input"' in response.data
    assert b'name="custom_topic"' in response.data
    assert b'id="date"' in response.data
    assert b'data-date-picker' in response.data
    assert b'date-picker__trigger' in response.data
    assert b"btn-busy" in response.data
    assert b"armStatusDismiss" in response.data
    assert b"STATUS_DISMISS_MS" in response.data
    assert b'id="start_time"' in response.data
    assert b'id="end_time"' in response.data
    assert b'value="09:30"' in response.data
    assert b'value="15:30"' in response.data
    assert b"90 min" in response.data
    assert b'data-session-start' in response.data
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
    assert body["end_time"] == "10:30"
    assert body["capacity"] == 50
    assert body["hall_label"] == "Conference Room (50 seats)"


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
    assert request_body["hall_label"] == "Grand Hall (100 seats)"

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
    assert portal["events"][0]["hall_label"] == "Grand Hall (100 seats)"
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


def test_enhance_abstract_accepts_dashboard_session_keys(client):
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
    assert response.status_code == 200
    body = response.get_json()
    assert body["fallback"] is True
    assert "Ollama could not be reached" in body["message"]
    assert body["abstract"] == "A practical walkthrough of commands and queries."
    assert "This conference session covers" not in body["abstract"]


def test_enhance_abstract_falls_back_when_ollama_is_offline(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/enhance-abstract",
        json={"abstract": "A practical walkthrough of commands and queries."},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["fallback"] is True
    assert body["model"] == "local-fallback"
    assert body["abstract"] == "A practical walkthrough of commands and queries."
    assert "This conference session covers" not in body["abstract"]
    assert "error" not in body


def test_enhance_abstract_uses_ollama_generate_api(client, app, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)
    app.config["OLLAMA_MODEL"] = "llama3"
    captured = {}

    def fake_generate(prompt, **kwargs):
        captured["prompt"] = prompt
        captured["max_tokens"] = kwargs.get("max_tokens")
        captured["timeout"] = kwargs.get("timeout")
        captured["temperature"] = kwargs.get("temperature")
        captured["stream"] = kwargs.get("stream")
        captured["keep_alive"] = kwargs.get("keep_alive")
        captured["num_ctx"] = kwargs.get("num_ctx")
        return "A polished conference abstract on CQRS for event organizers."

    monkeypatch.setattr("services.abstract_enhancer.generate", fake_generate)
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
    assert body["model"] == "llama3"
    assert captured["max_tokens"] == 100
    assert captured["timeout"] == 9
    assert captured["temperature"] == 0.3
    assert captured["stream"] is True
    assert captured["keep_alive"] == "30m"
    assert captured["num_ctx"] == 512
    assert "2-3 sentence" in captured["prompt"]
    assert "A practical walkthrough of commands and queries." in captured["prompt"]
    assert "This conference session covers" not in body["abstract"]


def test_enhance_abstract_extracts_generated_text_shapes(client, monkeypatch):
    _register_speaker(client, user_id="spk-parse", name="Parse Speaker")
    _login_speaker(client, user_id="spk-parse")
    expected = "A polished conference abstract on CQRS for event organizers."
    shapes = [
        expected,
        {"response": expected},
        {"generated_text": expected},
        [{"generated_text": expected}],
        json.dumps([{"response": expected}]),
    ]

    for shape in shapes:
        monkeypatch.setattr(
            "services.abstract_enhancer.generate",
            lambda prompt, current=shape, **kwargs: current,
        )
        response = client.post(
            "/api/enhance-abstract",
            json={"abstract": "A practical walkthrough of commands and queries."},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["enhanced_abstract"] == expected
        assert body["abstract"] == expected


def test_enhance_abstract_falls_back_when_ollama_is_unreachable(client, monkeypatch):
    from services.ollama import OllamaError

    _register_speaker(client)
    _login_speaker(client)

    def boom(prompt, **kwargs):
        raise OllamaError("Ollama could not be reached: connection refused", status_code=503)

    monkeypatch.setattr("services.abstract_enhancer.generate", boom)
    response = client.post(
        "/api/enhance-abstract",
        json={
            "title": "Building CQRS with Flask",
            "category": "architecture",
            "abstract": "a practical walkthrough of commands and queries",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["fallback"] is True
    assert body["model"] == "local-fallback"
    assert body["abstract"] == "a practical walkthrough of commands and queries"
    assert "This conference session covers" not in body["abstract"]
    assert "is an architecture session" not in body["abstract"]
    assert "Ollama could not be reached" in body["message"]
    assert "error" not in body


def test_enhance_abstract_falls_back_on_ollama_errors(client, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)

    def boom(prompt, **kwargs):
        raise RuntimeError("model llama3 is currently loading")

    monkeypatch.setattr("services.abstract_enhancer.generate", boom)
    result = client.post(
        "/api/enhance-abstract",
        json={
            "title": "Building CQRS with Flask",
            "category": "architecture",
            "abstract": "a practical walkthrough of commands and queries",
        },
    )
    assert result.status_code == 200
    body = result.get_json()
    assert body["fallback"] is True
    assert body["model"] == "local-fallback"
    assert body["enhanced_abstract"] == "a practical walkthrough of commands and queries"
    assert "This conference session covers" not in body["enhanced_abstract"]
    assert "error" not in body


def test_speaker_can_reply_to_admin_from_chat(client, app, speaker_headers, speaker_id):
    with app.app_context():
        notice = ChatMessage(
            id=str(uuid4()),
            recipient_id=speaker_id,
            recipient_role="speaker",
            sender_id=admin_organizer_id(),
            sender_role="organizer",
            subject="Event cancelled",
            kind="event_cancelled",
            body='Your event "Keynote" has been cancelled by the organizer.',
        )
        db.session.add(notice)
        db.session.commit()
        notice_id = notice.id

    inbox = client.get("/api/speaker/messages", headers=speaker_headers)
    assert inbox.status_code == 200
    payload = inbox.get_json()
    assert payload["unread_count"] == 1
    assert payload["messages"][0]["subject"] == "Event cancelled"
    assert payload["messages"][0]["from_label"] == "Event Organizer"

    opened = client.post(
        "/api/speaker/messages/read",
        json={"message_id": notice_id},
        headers=speaker_headers,
    )
    assert opened.status_code == 200
    opened_body = opened.get_json()
    assert opened_body["unread_count"] == 0
    assert opened_body["thread"][0]["id"] == notice_id

    reply = client.post(
        "/api/speaker/messages",
        json={"body": "Thanks, I will update my calendar.", "parent_id": notice_id},
        headers=speaker_headers,
    )
    assert reply.status_code == 201
    reply_body = reply.get_json()
    assert reply_body["message"]["kind"] == "speaker_reply"
    assert reply_body["message"]["recipient_id"] == admin_organizer_id()
    assert reply_body["message"]["recipient_role"] == "organizer"
    assert reply_body["message"]["from_label"] == "You"
    assert any(
        item["body"] == "Thanks, I will update my calendar." for item in reply_body["thread"]
    )

    with app.app_context():
        stored = ChatMessage.query.filter_by(kind="speaker_reply", parent_id=notice_id).one()
        assert stored.recipient_role == "organizer"
        assert stored.sender_id == speaker_id

    admin_headers = {"X-Organizer-Id": admin_organizer_id()}
    admin_inbox = client.get("/api/organizer/messages", headers=admin_headers)
    assert admin_inbox.status_code == 200
    admin_payload = admin_inbox.get_json()
    assert admin_payload["unread_count"] >= 1
    assert any("calendar" in item["body"] for item in admin_payload["messages"])
    assert any(item.get("peer_id") == speaker_id for item in admin_payload["messages"])
    assert all(item.get("subject") != "Event cancelled" for item in admin_payload["messages"])
    assert all(item.get("peer_name") for item in admin_payload["messages"])

    admin_reply = client.post(
        "/api/organizer/messages",
        json={"body": "Understood, the refund is already in motion.", "parent_id": notice_id},
        headers=admin_headers,
    )
    assert admin_reply.status_code == 201
    admin_reply_body = admin_reply.get_json()
    assert admin_reply_body["message"]["kind"] == "organizer_reply"
    assert admin_reply_body["message"]["recipient_id"] == speaker_id
    assert admin_reply_body["message"]["from_label"] == "You"
    assert any("refund is already in motion" in item["body"] for item in admin_reply_body["thread"])

    speaker_followup = client.get("/api/speaker/messages", headers=speaker_headers).get_json()
    assert speaker_followup["unread_count"] >= 1
    thread = client.post(
        "/api/speaker/messages/read",
        json={"message_id": notice_id},
        headers=speaker_headers,
    ).get_json()["thread"]
    bodies = [item["body"] for item in thread]
    assert "Thanks, I will update my calendar." in bodies
    assert "Understood, the refund is already in motion." in bodies
