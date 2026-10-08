from services.auth import admin_organizer_id

from conftest import approve_talk_event


def _admin_headers():
    return {"X-Organizer-Id": admin_organizer_id()}


def test_manual_event_create_is_removed(client, organizer_headers, event_payload):
    response = client.post(
        "/api/organizer/events",
        json=event_payload,
        headers=organizer_headers,
    )
    assert response.status_code == 405


def test_list_events_with_header_identity(client, created_event):
    response = client.get("/api/organizer/events", headers=_admin_headers())

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]


def test_list_events_with_query_identity(client, created_event):
    response = client.get(
        "/api/organizer/events",
        query_string={"organizer_id": admin_organizer_id()},
    )

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]


def test_list_events_requires_identity(client):
    response = client.get("/api/organizer/events")

    assert response.status_code == 400
    assert "organizer_id" in response.get_json()["error"]


def test_list_speakers_returns_registered_speakers(client, app):
    from extensions import db
    from models.speaker import Speaker

    with app.app_context():
        db.session.add(Speaker(id="spk-maya", name="Maya Cohen"))
        db.session.add(Speaker(id="spk-omar", name="Omar Hassan"))
        db.session.commit()

    response = client.get("/api/organizer/speakers")

    assert response.status_code == 200
    speakers = response.get_json()
    assert [speaker["id"] for speaker in speakers] == ["spk-maya", "spk-omar"]
    assert speakers[0]["name"] == "Maya Cohen"


def test_approve_proposal_creates_event_with_speaker(client, speaker_headers, speaker_id, event_payload):
    event = approve_talk_event(client, speaker_headers, event_payload)
    assert event["speaker_id"] == speaker_id
    assert event["title"] == event_payload["title"]
    assert event["status"] == "approved"
    assert event["organizer_id"] == admin_organizer_id()


def test_organizer_stats_counts_attendees_and_held_events(
    client, speaker_headers, event_payload, attendee_headers
):
    past = approve_talk_event(
        client, speaker_headers, event_payload, title="Past Summit", date="2020-01-15"
    )
    approve_talk_event(
        client, speaker_headers, event_payload, title="Future Summit", date="2099-06-01"
    )
    registered = client.post(
        "/api/attendee/register",
        json={"event_id": past["id"], "seats": 1},
        headers=attendee_headers,
    )
    assert registered.status_code == 201

    response = client.get("/api/organizer/stats", headers=_admin_headers())
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["attendees"] == 1
    assert stats["events_held"] == 1
    assert stats["active_events"] == 2
    assert "occupancy" not in stats
    assert "/" not in str(stats["attendees"])


def test_list_events_is_sorted_by_date_and_time_ascending(client, speaker_headers, event_payload):
    approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="December Talk",
        date="2026-12-01",
        start_time="14:00",
        end_time="15:00",
    )
    approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="November Evening",
        date="2026-11-01",
        start_time="16:00",
        end_time="17:00",
    )
    approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="November Morning",
        date="2026-11-01",
        start_time="09:00",
        end_time="10:00",
    )

    response = client.get("/api/organizer/events", headers=_admin_headers())
    assert response.status_code == 200
    titles = [item["title"] for item in response.get_json()]
    assert titles == ["November Morning", "November Evening", "December Talk"]


def test_list_events_is_scoped_to_organizer(client, created_event):
    admin = client.get("/api/organizer/events", headers=_admin_headers())
    other = client.get("/api/organizer/events", headers={"X-Organizer-Id": "org-2"})

    assert admin.status_code == 200
    assert len(admin.get_json()) == 1
    assert admin.get_json()[0]["id"] == created_event["id"]
    assert other.status_code == 200
    assert other.get_json() == []
