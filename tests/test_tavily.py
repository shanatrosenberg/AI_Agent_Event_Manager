from services.tavily import VERIFIED_BADGE, simulated_tavily_verification, verify_speaker_and_talk


class _FakeResponse:
    status_code = 200
    content = b"{}"

    def raise_for_status(self):
        return None

    def json(self):
        return {
            "answer": "Ada Lovelace published notes on the analytical engine.",
            "results": [
                {
                    "title": "Ada Lovelace biography",
                    "url": "https://example.com/ada",
                    "content": "Early computing publications and notes on the analytical engine.",
                }
            ],
        }


def test_simulated_fallback_is_verified():
    result = simulated_tavily_verification("Ada Lovelace CQRS", "Ada Lovelace", "CQRS Talk")
    assert result["verified"] is True
    assert result["verification_badge"] == VERIFIED_BADGE
    assert result["fallback"] is True


def test_verify_speaker_and_talk_sets_badge(monkeypatch, app):
    monkeypatch.setattr("services.tavily.tavily_api_key", lambda: "tvly-test")
    monkeypatch.setattr("services.tavily.requests.post", lambda *args, **kwargs: _FakeResponse())
    result = verify_speaker_and_talk("Ada Lovelace", "Analytical Engines")
    assert result["enabled"] is True
    assert result["verified"] is True
    assert result["verification_badge"] == VERIFIED_BADGE
    assert result["results"][0]["title"] == "Ada Lovelace biography"
    assert "analytical engine" in result["summary"].lower()
    assert "Ada Lovelace" in result["query"]
    assert "Analytical Engines" in result["query"]


def test_submit_persists_tavily_verification(client, monkeypatch):
    monkeypatch.setattr("services.tavily.tavily_api_key", lambda: "tvly-test")
    monkeypatch.setattr("services.tavily.requests.post", lambda *args, **kwargs: _FakeResponse())
    client.post(
        "/register",
        json={
            "user_id": "spk-tavily",
            "password": "SecurePass1",
            "role": "speaker",
            "name": "Ada Lovelace",
        },
    )
    client.post("/speaker/login", json={"user_id": "spk-tavily", "password": "SecurePass1"})
    created = client.post(
        "/api/submit",
        json={
            "title": "Analytical Engines",
            "abstract": "A talk about early computing publications and program design.",
            "category": "history",
            "date": "2026-12-22",
            "start_time": "10:00",
            "end_time": "11:00",
            "capacity": 50,
        },
    ).get_json()
    assert created["tavily_verified"] is True
    assert created["tavily_badge"] == VERIFIED_BADGE
    web = created["ai_assessment"]["web_check"]
    assert web["verified"] is True
    assert web["results"][0]["snippet"]
    assert created["ai_assessment"]["hooks"]["mcp_tavily"]["enabled"] is True
