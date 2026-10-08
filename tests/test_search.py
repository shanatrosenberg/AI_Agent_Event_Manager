from models.embedding import TalkEmbedding
from services.embeddings import cosine_similarity, embed_local, proposal_document


def _register_speaker(client, user_id="spk-search", name="Search Speaker"):
    return client.post(
        "/register",
        json={
            "user_id": user_id,
            "password": "SecurePass1",
            "role": "speaker",
            "name": name,
        },
    )


def _login_speaker(client, user_id="spk-search"):
    return client.post("/speaker/login", json={"user_id": user_id, "password": "SecurePass1"})


def _submit(client, **overrides):
    payload = {
        "title": "Building CQRS with Flask",
        "abstract": "A practical walkthrough of commands, queries, and event sourcing for conference systems.",
        "category": "architecture",
        "date": "2026-11-12",
        "start_time": "11:00",
        "end_time": "12:00",
        "capacity": 100,
    }
    payload.update(overrides)
    return client.post("/api/submit", json=payload)


def test_local_embeddings_rank_similar_text_higher():
    cqrs = embed_local("commands queries event sourcing flask architecture")
    similar = embed_local(proposal_document(title="CQRS", abstract="event sourcing and queries in flask"))
    other = embed_local(proposal_document(title="Pastry workshop", abstract="baking sourdough bread and cakes"))
    assert cosine_similarity(cqrs, similar) > cosine_similarity(cqrs, other)


def test_submit_indexes_proposal_for_semantic_search(client):
    _register_speaker(client)
    _login_speaker(client)
    created = _submit(client).get_json()
    row = TalkEmbedding.query.filter_by(source_type="proposal", source_id=created["id"]).first()
    assert row is not None
    assert row.embedding
    assert "CQRS" in row.document_text or "commands" in row.document_text


def test_semantic_search_ranks_relevant_talk_first(client):
    _register_speaker(client)
    _login_speaker(client)
    cqrs_talk = _submit(
        client,
        title="Event sourcing with CQRS",
        abstract="Commands, queries, and an event store for Flask conference platforms.",
        category="architecture",
    ).get_json()
    _submit(
        client,
        title="Sourdough baking for beginners",
        abstract="A hands-on kitchen workshop about bread, pastry, and fermentation.",
        category="food",
        date="2026-11-13",
        start_time="13:00",
        end_time="14:00",
    )

    response = client.get("/api/search", query_string={"q": "event sourcing CQRS flask queries", "limit": 5})
    assert response.status_code == 200
    body = response.get_json()
    assert body["count"] >= 1
    top = body["results"][0]
    assert top["id"] == cqrs_talk["id"]
    assert top["source_type"] == "proposal"
    assert top["score"] > 0

    organizer = client.get(
        "/api/organizer/search",
        query_string={"q": "commands and queries in an event store", "type": "proposal"},
        headers={"X-Organizer-Id": "org-admin"},
    )
    assert organizer.status_code == 200
    assert organizer.get_json()["results"][0]["id"] == cqrs_talk["id"]

    attendee = client.post("/api/attendee/search", json={"query": "CQRS event sourcing architecture"})
    assert attendee.status_code == 200
    assert attendee.get_json()["results"] == []


def test_semantic_search_requires_query(client):
    response = client.get("/api/search")
    assert response.status_code == 400
    assert response.get_json()["error"] == "query is required"
