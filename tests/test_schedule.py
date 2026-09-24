from conftest import approve_talk_event


def test_submit_talk_requires_schedule_fields(client, speaker_headers, talk_payload):
    payload = {**talk_payload}
    payload.pop("start_time")
    response = client.post("/api/speaker/submit", json=payload, headers=speaker_headers)
    assert response.status_code == 400
    assert "start_time" in response.get_json()["error"] or "Hall" in response.get_json()["error"] or "date" in response.get_json()["error"]


def test_submit_talk_rejects_invalid_hall(client, speaker_headers, talk_payload):
    response = client.post(
        "/api/speaker/submit",
        json={**talk_payload, "capacity": 75},
        headers=speaker_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Hall capacity must be 50, 100, or 300 seats."


def test_submit_talk_rejects_end_before_start(client, speaker_headers, talk_payload):
    response = client.post(
        "/api/speaker/submit",
        json={**talk_payload, "start_time": "11:00", "end_time": "10:00"},
        headers=speaker_headers,
    )
    assert response.status_code == 400
    assert "end_time" in response.get_json()["error"]


def test_approve_rejects_hall_time_conflict(client, speaker_headers, event_payload):
    first = approve_talk_event(client, speaker_headers, event_payload)
    assert first["status"] == "approved"
    second = client.post(
        "/api/speaker/submit",
        json={
            "title": "Overlap",
            "abstract": event_payload["description"],
            "category": "general",
            "date": event_payload["date"],
            "start_time": "09:30",
            "end_time": "10:30",
            "capacity": event_payload["capacity"],
        },
        headers=speaker_headers,
    )
    assert second.status_code == 201
    conflict = client.post(f"/api/organizer/proposals/{second.get_json()['id']}/approve")
    assert conflict.status_code == 409
    assert "already booked" in conflict.get_json()["error"]


def test_approve_allows_adjacent_slot_and_other_hall(client, speaker_headers, event_payload):
    first = approve_talk_event(client, speaker_headers, event_payload)
    assert first["status"] == "approved"
    adjacent = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Next slot",
        start_time="10:00",
        end_time="11:00",
    )
    other_hall = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Other hall",
        capacity=100,
    )
    assert adjacent["start_time"] == "10:00"
    assert other_hall["capacity"] == 100


def test_update_event_rejects_conflict_and_allows_self(client, speaker_headers, event_payload, created_event):
    other = approve_talk_event(
        client,
        speaker_headers,
        event_payload,
        title="Later",
        start_time="11:00",
        end_time="12:00",
    )
    assert other["id"] != created_event["id"]

    same = client.put(
        f"/api/organizer/events/{created_event['id']}",
        json={**event_payload, "title": "Updated Summit"},
        headers={"X-Organizer-Id": created_event["organizer_id"]},
    )
    assert same.status_code == 200
    assert same.get_json()["title"] == "Updated Summit"

    conflict = client.put(
        f"/api/organizer/events/{created_event['id']}",
        json={**event_payload, "start_time": "11:00", "end_time": "12:30"},
        headers={"X-Organizer-Id": created_event["organizer_id"]},
    )
    assert conflict.status_code == 409
    assert "already booked" in conflict.get_json()["error"]


def test_approved_events_api_and_page(client, created_event):
    api = client.get("/api/attendee/approved")
    assert api.status_code == 200
    events = api.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]
    assert events[0]["display_status"] == "Approved"

    page = client.get("/approved")
    assert page.status_code == 200
    assert b"Approved events" in page.data
