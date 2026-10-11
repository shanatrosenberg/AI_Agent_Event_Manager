from services.idea_hub import _parse_generated_idea, category_for_topic, curated_ideas


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


def test_curated_ideas_cover_trending_topics():
    ideas = curated_ideas(6)
    topics = {item["topic"] for item in ideas}
    assert {"AI Agents", "Cloud Security", "RAG"} <= topics
    assert all(item["title"] and item["abstract"] and item["id"] for item in ideas)


def test_curated_ideas_follow_custom_topic_query():
    ideas = curated_ideas(4, query="Microservices")
    assert len(ideas) == 4
    assert all("Microservices" in item["topic"] or "Microservices" in item["title"] for item in ideas)
    assert category_for_topic("Microservices") == "architecture"
    assert category_for_topic("AI Agents") == "ai"


def test_parse_generated_idea_accepts_title_abstract_format():
    parsed = _parse_generated_idea(
        "TITLE: Agents in production\nABSTRACT: How to ship safe AI agents for conference review.",
        "AI Agents",
        "ai",
    )
    assert parsed["title"] == "Agents in production"
    assert "safe AI agents" in parsed["abstract"]
    assert parsed["topic"] == "AI Agents"
    assert parsed["category"] == "ai"


def test_innovation_ideas_require_speaker_login(client):
    response = client.get("/api/speaker/innovation-ideas")
    assert response.status_code == 401


def test_innovation_ideas_return_curated_fallback_when_ollama_is_offline(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.get("/api/speaker/innovation-ideas")
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "curated"
    assert body.get("fallback") is True
    assert len(body["ideas"]) == 6
    topics = {item["topic"] for item in body["ideas"]}
    assert {"AI Agents", "Cloud Security", "RAG"} <= topics
    first = body["ideas"][0]
    assert first["title"]
    assert first["abstract"]
    assert first["category"]
    assert first["id"].startswith("idea-")


def test_innovation_ideas_use_ollama_when_available(client, app, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)
    app.config["OLLAMA_MODEL"] = "llama3"
    prompts = []

    def fake_generate(prompt, **kwargs):
        prompts.append(prompt)
        topic = "RAG" if "RAG" in prompt else "AI Agents"
        if "Cloud Security" in prompt:
            topic = "Cloud Security"
        return (
            f"TITLE: Live {topic} session\n"
            f"ABSTRACT: A cutting-edge conference talk about {topic} for event organizers."
        )

    monkeypatch.setattr("services.idea_hub.generate", fake_generate)
    response = client.get("/api/speaker/innovation-ideas?limit=3")
    assert response.status_code == 200
    body = response.get_json()
    assert body["source"] == "ollama"
    assert body["model"] == "llama3"
    assert len(body["ideas"]) == 3
    assert all(item["title"].startswith("Live ") for item in body["ideas"])
    assert len(prompts) == 3


def test_innovation_ideas_accept_custom_topic_query(client):
    _register_speaker(client)
    _login_speaker(client)
    response = client.post(
        "/api/speaker/innovation-ideas",
        json={"query": "Microservices", "limit": 4},
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["query"] == "Microservices"
    assert body["source"] == "curated"
    assert len(body["ideas"]) == 4
    assert all(
        "Microservices" in item["topic"] or "Microservices" in item["title"] or "Microservices" in item["abstract"]
        for item in body["ideas"]
    )


def test_innovation_ideas_pass_query_to_ollama(client, app, monkeypatch):
    _register_speaker(client)
    _login_speaker(client)
    prompts = []

    def fake_generate(prompt, **kwargs):
        prompts.append(prompt)
        return "TITLE: Mesh without the mess\nABSTRACT: A cutting-edge conference talk about microservices for event platforms."

    monkeypatch.setattr("services.idea_hub.generate", fake_generate)
    response = client.get("/api/speaker/innovation-ideas?q=Microservices&limit=3")
    assert response.status_code == 200
    body = response.get_json()
    assert body["query"] == "Microservices"
    assert body["source"] == "ollama"
    assert len(body["ideas"]) == 3
    assert all(item["topic"] == "Microservices" for item in body["ideas"])
    assert all("Microservices" in prompt for prompt in prompts)
