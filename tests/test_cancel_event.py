from conftest import approve_talk_event
from models.booking import Booking
from models.chat_message import ChatMessage
from models.stored_event import StoredEvent
from services.auth import admin_organizer_id


def _admin_headers():
    return {"X-Organizer-Id": admin_organizer_id()}


def test_program_payload_includes_hall_seats_and_abstract(
    client, speaker_headers, event_payload
):
    event = approve_talk_event(client, speaker_headers, event_payload, title="Detail payload talk")
    listed = client.get("/api/organizer/events", headers=_admin_headers())
    assert listed.status_code == 200
    match = next(item for item in listed.get_json() if item["id"] == event["id"])
    assert match["abstract"]
    assert match["seats_label"].startswith("50 open /")
    assert match["hall_configuration"]["capacity"] == 50
    assert match["speaker"]["id"] == event["speaker_id"]

    detail = client.get(f"/api/organizer/events/{event['id']}", headers=_admin_headers())
    assert detail.status_code == 200
    body = detail.get_json()
    assert body["id"] == event["id"]
    assert "Tickets purchased" not in body
    assert body["open_seats"] == 50
    assert body["sold_seats"] == 0

    speaker = client.get(f"/api/speaker/events/{event['id']}", headers=speaker_headers)
    assert speaker.status_code == 200
    assert speaker.get_json()["abstract"] == body["abstract"]


def test_speaker_my_events_lists_only_approved_sessions(
    client, speaker_headers, event_payload, speaker_id
):
    live = approve_talk_event(client, speaker_headers, event_payload, title="Live approved talk")
    doomed = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Doomed approved talk",
        date="2026-12-01",
        start_time="14:00",
        end_time="15:00",
    )
    cancelled = client.post(f"/api/organizer/events/{doomed['id']}/cancel", headers=_admin_headers())
    assert cancelled.status_code == 200

    portal = client.get("/api/speaker/portal", headers=speaker_headers)
    assert portal.status_code == 200
    events = portal.get_json()["events"]
    ids = {item["id"] for item in events}
    assert live["id"] in ids
    assert doomed["id"] not in ids
    assert all(item["status"] in {"approved", "active"} for item in events)

    listed = client.get("/api/speaker/events", headers=speaker_headers)
    assert listed.status_code == 200
    listed_ids = {item["id"] for item in listed.get_json()["events"]}
    assert live["id"] in listed_ids
    assert doomed["id"] not in listed_ids


def test_admin_can_cancel_approved_event_and_notify_buyers_and_lecturer(
    client, app, speaker_headers, event_payload, attendee_headers, attendee_id, speaker_id
):
    event = approve_talk_event(client, speaker_headers, event_payload, title="Evening keynote")
    booked = client.post(
        "/api/attendee/register",
        json={"event_id": event["id"], "seats": 1},
        headers=attendee_headers,
    )
    assert booked.status_code == 201

    cancelled = client.post(f"/api/organizer/events/{event['id']}/cancel", headers=_admin_headers())
    assert cancelled.status_code == 200
    body = cancelled.get_json()
    assert body["id"] == event["id"]
    assert body["status"] == "cancelled"
    assert body["display_status"] == "Cancelled"

    trash = client.get("/api/organizer/trash", headers=_admin_headers()).get_json()
    assert any(item.get("event_id") == event["id"] or item.get("id") == event["id"] for item in trash)
    assert any(item.get("kind") == "cancelled_event" and item.get("id") == event["id"] for item in trash)

    program = client.get("/api/organizer/events", headers=_admin_headers()).get_json()
    assert all(item["id"] != event["id"] for item in program)

    public = client.get("/api/attendee/approved").get_json()
    assert all(item["id"] != event["id"] for item in public)

    speaker_events = client.get("/api/speaker/events", headers=speaker_headers).get_json()["events"]
    assert all(item["id"] != event["id"] for item in speaker_events)

    speaker_notes = client.get("/api/speaker/messages", headers=speaker_headers)
    assert speaker_notes.status_code == 200
    speaker_payload = speaker_notes.get_json()
    assert speaker_payload["unread_count"] >= 1
    speaker_bodies = [item["body"] for item in speaker_payload["messages"]]
    assert any(item.get("unread") for item in speaker_payload["messages"])
    assert any(item.get("subject") == "Event cancelled" for item in speaker_payload["messages"])
    assert any("Evening keynote" in text and "cancelled" in text.lower() for text in speaker_bodies)
    marked = client.post("/api/speaker/messages/read", headers=speaker_headers)
    assert marked.status_code == 200
    assert marked.get_json()["unread_count"] == 0

    attendee_notes = client.get("/api/attendee/messages", headers=attendee_headers)
    assert attendee_notes.status_code == 200
    attendee_bodies = [item["body"] for item in attendee_notes.get_json()["messages"]]
    assert any(
        "Evening keynote" in text and "full refund" in text.lower() for text in attendee_bodies
    )

    with app.app_context():
        bookings = Booking.query.filter_by(event_id=event["id"]).all()
        assert bookings
        assert all(row.status == "refunded" for row in bookings)
        notices = ChatMessage.query.filter_by(event_id=event["id"]).all()
        roles = {row.recipient_role for row in notices}
        assert roles == {"attendee", "speaker"}
        names = {row.event_name for row in StoredEvent.query.all()}
        assert "EventCancelled" in names
        assert "ChatNotified" in names

    again = client.post(f"/api/organizer/events/{event['id']}/cancel", headers=_admin_headers())
    assert again.status_code == 409


def test_cannot_cancel_deleted_event(client, speaker_headers, event_payload):
    event = approve_talk_event(client, speaker_headers, event_payload, title="Temporary workshop")
    removed = client.delete(f"/api/organizer/events/{event['id']}", headers=_admin_headers())
    assert removed.status_code == 200
    cancelled = client.post(f"/api/organizer/events/{event['id']}/cancel", headers=_admin_headers())
    assert cancelled.status_code == 409


def test_lecturer_can_cancel_approved_event_and_notify_buyers(
    client, app, speaker_headers, event_payload, attendee_headers
):
    event = approve_talk_event(client, speaker_headers, event_payload, title="Lecturer cancel talk")
    booked = client.post(
        "/api/attendee/register",
        json={"event_id": event["id"], "seats": 1},
        headers=attendee_headers,
    )
    assert booked.status_code == 201

    cancelled = client.post(
        f"/api/speaker/events/{event['id']}/cancel",
        headers=speaker_headers,
    )
    assert cancelled.status_code == 200
    assert cancelled.get_json()["status"] == "cancelled"

    notes = client.get("/api/attendee/messages", headers=attendee_headers).get_json()["messages"]
    assert any("full refund" in item["body"].lower() for item in notes)
    admin_notes = client.get("/api/organizer/messages", headers=_admin_headers())
    assert admin_notes.status_code == 200
    admin_payload = admin_notes.get_json()
    assert admin_payload["unread_count"] >= 1
    assert any("cancelled" in item["body"].lower() for item in admin_payload["messages"])
    trash = client.get("/api/organizer/trash", headers=_admin_headers()).get_json()
    assert any(item.get("kind") == "cancelled_event" and item.get("id") == event["id"] for item in trash)
    assert all(
        item["id"] != event["id"]
        for item in client.get("/api/speaker/events", headers=speaker_headers).get_json()["events"]
    )
    assert all(item["id"] != event["id"] for item in client.get("/api/organizer/events", headers=_admin_headers()).get_json())


def test_organizer_dashboard_exposes_cancel_action(client):
    login = client.post("/login", json={"user_id": "admin", "password": "AdminPass!2026"})
    assert login.status_code == 200
    page = client.get("/organizer")
    assert page.status_code == 200
    assert b"Cancel Event" in page.data
    assert b"More Details" in page.data
    assert b"rejectEvent" not in page.data
    assert b"/events/${event.id}/reject" not in page.data
    assert b"Lecture summary" in page.data
    assert b"Hall specifications" not in page.data
    assert b">Open/Sold Seats</th>" in page.data
    assert b'id="event-detail-modal"' in page.data
    assert 'id="event-detail-modal" class="fixed inset-0 z-50 hidden' in page.get_data(as_text=True)
    assert b"/api/organizer/events/" in page.data
    assert b"/cancel" in page.data
    assert b'showTab("trash")' in page.data
    assert b"Trash / Recycling Bin" in page.data
    assert b'id="open-organizer-chat"' in page.data
    assert b'id="organizer-chat-unread-badge"' in page.data
    assert b'id="organizer-chat-sidebar"' in page.data
    assert b'id="organizer-chat-reply-form"' in page.data
    assert b"conversationTitle" in page.data
    assert b"Type a message" in page.data
    assert b'placeholder="Type a message' in page.data
    assert b"-right-1 -top-1" in page.data
    assert b"bg-emerald-500" in page.data
