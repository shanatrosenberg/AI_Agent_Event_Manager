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


def test_list_events_is_scoped_to_organizer(client, created_event):
    admin = client.get("/api/organizer/events", headers=_admin_headers())
    other = client.get("/api/organizer/events", headers={"X-Organizer-Id": "org-2"})

    assert admin.status_code == 200
    assert len(admin.get_json()) == 1
    assert admin.get_json()[0]["id"] == created_event["id"]
    assert other.status_code == 200
    assert other.get_json() == []
