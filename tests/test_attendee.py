def test_list_active_events_includes_created_event(client, created_event):
    response = client.get("/api/attendee/events")

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]
    assert events[0]["available"] is True


def test_list_active_events_is_empty_when_none_exist(client):
    response = client.get("/api/attendee/events")

    assert response.status_code == 200
    assert response.get_json() == []


def test_register_with_header_identity(client, attendee_headers, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": 2},
        headers=attendee_headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["attendee_id"] == attendee_id
    assert body["event_id"] == created_event["id"]
    assert body["seats"] == 2
    assert body["status"] == "confirmed"
    assert "id" in body


def test_register_with_body_identity(client, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "attendee_id": attendee_id},
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_id
    assert response.get_json()["seats"] == 1


def test_register_with_query_identity(client, attendee_id, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        query_string={"attendee_id": attendee_id},
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_id


def test_register_prefers_header_over_body(client, attendee_headers, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "attendee_id": "att-from-body"},
        headers=attendee_headers,
    )

    assert response.status_code == 201
    assert response.get_json()["attendee_id"] == attendee_headers["X-Attendee-Id"]


def test_register_requires_identity(client, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
    )

    assert response.status_code == 400
    assert "attendee_id" in response.get_json()["error"]


def test_register_requires_json_body(client, attendee_headers):
    response = client.post("/api/attendee/register", headers=attendee_headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body is required"


def test_register_rejects_missing_event_id(client, attendee_headers):
    response = client.post(
        "/api/attendee/register",
        json={"seats": 1},
        headers=attendee_headers,
    )

    assert response.status_code == 400
    assert "event_id" in response.get_json()["error"]


def test_register_rejects_invalid_seats(client, attendee_headers, created_event):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": "many"},
        headers=attendee_headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "seats must be an integer"


def test_register_unknown_event_returns_404(client, attendee_headers):
    response = client.post(
        "/api/attendee/register",
        json={"event_id": "missing-event"},
        headers=attendee_headers,
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "event not found"


def test_register_duplicate_returns_409(client, attendee_headers, created_event):
    first = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        headers=attendee_headers,
    )
    second = client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"]},
        headers=attendee_headers,
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert "already registered" in second.get_json()["error"]


def test_register_reduces_remaining_seats(client, attendee_headers, created_event):
    client.post(
        "/api/attendee/register",
        json={"event_id": created_event["id"], "seats": 5},
        headers=attendee_headers,
    )

    events = client.get("/api/attendee/events").get_json()
    matching = next(event for event in events if event["id"] == created_event["id"])
    assert matching["seats_booked"] == 5
    assert matching["remaining_seats"] == created_event["capacity"] - 5
