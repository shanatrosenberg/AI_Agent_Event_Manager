def test_submit_talk_with_header_identity(client, speaker_headers, speaker_id, talk_payload):
    response = client.post(
        "/api/speaker/submit",
        json=talk_payload,
        headers=speaker_headers,
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["speaker_id"] == speaker_id
    assert body["title"] == talk_payload["title"]
    assert body["abstract"] == talk_payload["abstract"]
    assert body["category"] == talk_payload["category"]
    assert body["status"] == "under_review"
    assert body["ai_assessment"]["queued_for_background_agent"] is True
    assert "id" in body


def test_submit_talk_with_body_identity(client, speaker_id, talk_payload):
    payload = {**talk_payload, "speaker_id": speaker_id}

    response = client.post("/api/speaker/submit", json=payload)

    assert response.status_code == 201
    assert response.get_json()["speaker_id"] == speaker_id


def test_submit_talk_with_query_identity(client, speaker_id, talk_payload):
    response = client.post(
        "/api/speaker/submit",
        json=talk_payload,
        query_string={"speaker_id": speaker_id},
    )

    assert response.status_code == 201
    assert response.get_json()["speaker_id"] == speaker_id


def test_submit_talk_prefers_header_over_body(client, speaker_headers, talk_payload):
    payload = {**talk_payload, "speaker_id": "spk-from-body"}

    response = client.post(
        "/api/speaker/submit",
        json=payload,
        headers=speaker_headers,
    )

    assert response.status_code == 201
    assert response.get_json()["speaker_id"] == speaker_headers["X-Speaker-Id"]


def test_submit_talk_requires_identity(client, talk_payload):
    response = client.post("/api/speaker/submit", json=talk_payload)

    assert response.status_code == 400
    assert "Sign in as a speaker" in response.get_json()["error"]


def test_submit_talk_requires_json_body(client, speaker_headers):
    response = client.post("/api/speaker/submit", headers=speaker_headers)

    assert response.status_code == 400
    assert response.get_json()["error"] == "JSON body is required"


def test_submit_talk_rejects_invalid_hall(client, speaker_headers, talk_payload):
    response = client.post(
        "/api/speaker/submit",
        json={**talk_payload, "capacity": 75},
        headers=speaker_headers,
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Hall capacity must be 50, 100, or 300 seats."


def test_submit_talk_rejects_missing_fields(client, speaker_headers):
    response = client.post(
        "/api/speaker/submit",
        json={"title": "Only title"},
        headers=speaker_headers,
    )

    assert response.status_code == 400
    error = response.get_json()["error"]
    assert "Missing required fields" in error
    assert "abstract" in error
    assert "category" in error
    assert "date" in error
    assert "start_time" in error
    assert "end_time" in error
    assert "capacity" in error


def test_list_submissions_returns_speaker_talks(client, speaker_headers, speaker_id, talk_payload):
    created = client.post(
        "/api/speaker/submit",
        json=talk_payload,
        headers=speaker_headers,
    ).get_json()

    response = client.get(f"/api/speaker/submissions/{speaker_id}")

    assert response.status_code == 200
    body = response.get_json()
    assert body["speaker_id"] == speaker_id
    assert len(body["submissions"]) == 1
    assert body["submissions"][0]["id"] == created["id"]


def test_list_submissions_is_scoped_to_speaker(client, speaker_headers, speaker_id, talk_payload):
    client.post("/api/speaker/submit", json=talk_payload, headers=speaker_headers)
    client.post(
        "/api/speaker/submit",
        json={**talk_payload, "title": "Other Speaker Talk"},
        headers={"X-Speaker-Id": "spk-2"},
    )

    response = client.get(f"/api/speaker/submissions/{speaker_id}")

    assert response.status_code == 200
    submissions = response.get_json()["submissions"]
    assert len(submissions) == 1
    assert submissions[0]["speaker_id"] == speaker_id
    assert submissions[0]["title"] == talk_payload["title"]


def test_list_submissions_returns_empty_list_for_unknown_speaker(client):
    response = client.get("/api/speaker/submissions/unknown-speaker")

    assert response.status_code == 200
    body = response.get_json()
    assert body["speaker_id"] == "unknown-speaker"
    assert body["submissions"] == []
