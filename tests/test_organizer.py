def test_create_event_with_header_identity(client, organizer_headers, organizer_id, event_payload):
    response = client.post(
        "/api/organizer/events",
        json=event_payload,
        headers=organizer_headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["organizer_id"] == organizer_id
    assert body["title"] == event_payload["title"]
    assert body["capacity"] == event_payload["capacity"]
    assert body["status"] == "active"
    assert body["remaining_seats"] == event_payload["capacity"]
    assert "id" in body


def test_create_event_with_body_identity(client, organizer_id, event_payload):
    payload = {**event_payload, "organizer_id": organizer_id}

    response = client.post("/api/organizer/events", json=payload)

    assert response.status_code == 201
    assert response.get_json()["organizer_id"] == organizer_id


def test_create_event_with_query_identity(client, organizer_id, event_payload):
    response = client.post(
        "/api/organizer/events",
        json=event_payload,
        query_string={"organizer_id": organizer_id},
    )

    assert response.status_code == 201
    assert response.get_json()["organizer_id"] == organizer_id


def test_create_event_prefers_header_over_body(client, organizer_headers, event_payload):
    payload = {**event_payload, "organizer_id": "org-from-body"}

    response = client.post(
        "/api/organizer/events",
        json=payload,
        headers=organizer_headers,
    )

    assert response.status_code == 201
    assert response.get_json()["organizer_id"] == organizer_headers["X-Organizer-Id"]


def test_create_event_requires_identity(client, event_payload):
    response = client.post("/api/organizer/events", json=event_payload)

    assert response.status_code == 400
    assert "organizer_id" in response.get_json()["error"]


def test_create_event_requires_json_body(client, organizer_headers):
    response = client.post("/api/organizer/events", headers=organizer_headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body is required"


def test_create_event_rejects_missing_fields(client, organizer_headers):
    response = client.post(
        "/api/organizer/events",
        json={"title": "Only title"},
        headers=organizer_headers,
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "Missing required fields" in error
    assert "description" in error
    assert "date" in error
    assert "capacity" in error


def test_create_event_rejects_invalid_capacity(client, organizer_headers, event_payload):
    invalid_payload = {**event_payload, "capacity": "plenty"}
    response = client.post(
        "/api/organizer/events",
        json=invalid_payload,
        headers=organizer_headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "capacity must be an integer"


def test_create_event_rejects_zero_capacity(client, organizer_headers, event_payload):
    invalid_payload = {**event_payload, "capacity": 0}
    response = client.post(
        "/api/organizer/events",
        json=invalid_payload,
        headers=organizer_headers,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "capacity must be at least 1"


def test_list_events_with_header_identity(client, organizer_headers, created_event):
    response = client.get("/api/organizer/events", headers=organizer_headers)

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]


def test_list_events_with_query_identity(client, organizer_id, created_event):
    response = client.get(
        "/api/organizer/events",
        query_string={"organizer_id": organizer_id},
    )

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["id"] == created_event["id"]


def test_list_events_requires_identity(client):
    response = client.get("/api/organizer/events")

    assert response.status_code == 400
    assert "organizer_id" in response.get_json()["error"]


def test_list_events_is_scoped_to_organizer(client, organizer_headers, event_payload):
    client.post("/api/organizer/events", json=event_payload, headers=organizer_headers)
    client.post(
        "/api/organizer/events",
        json={**event_payload, "title": "Other Org Event"},
        headers={"X-Organizer-Id": "org-2"},
    )

    response = client.get("/api/organizer/events", headers=organizer_headers)

    assert response.status_code == 200
    events = response.get_json()
    assert len(events) == 1
    assert events[0]["organizer_id"] == organizer_headers["X-Organizer-Id"]
    assert events[0]["title"] == event_payload["title"]
