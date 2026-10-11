from services.abstract_enhancer import build_enhancement_prompt
from services.ollama import extract_generated_text, ollama_model, ollama_url


def test_ollama_defaults_point_at_local_generate(app):
    assert ollama_url() == "http://127.0.0.1:11434/api/generate"
    assert ollama_model() == "llama3"


def test_ollama_url_appends_generate_path(app):
    app.config["OLLAMA_URL"] = "http://127.0.0.1:11434"
    assert ollama_url() == "http://127.0.0.1:11434/api/generate"
    app.config["OLLAMA_URL"] = "http://127.0.0.1:11434/api/generate"
    assert ollama_url() == "http://127.0.0.1:11434/api/generate"


def test_ollama_url_rewrites_localhost_to_ipv4(app):
    app.config["OLLAMA_URL"] = "http://localhost:11434/api/generate"
    assert ollama_url() == "http://127.0.0.1:11434/api/generate"


def test_enhancement_prompt_asks_for_a_professional_abstract():
    prompt = build_enhancement_prompt(
        "Hands-on CQRS for event platforms.",
        title="Building CQRS with Flask",
        category="architecture",
    )
    assert prompt.startswith("Act as a professional conference content writer.")
    assert "3-4 sentences" in prompt
    assert "Hands-on CQRS for event platforms." in prompt
    assert "This conference session covers" not in prompt


def test_extract_ollama_response_payload():
    assert extract_generated_text({"response": "Hello from llama3"}) == "Hello from llama3"
    assert extract_generated_text({"generated_text": "Polished abstract."}) == "Polished abstract."


def test_generate_posts_local_model_without_streaming(app, monkeypatch):
    from services.ollama import generate

    captured = {}

    class FakeResponse:
        status_code = 200
        text = ""

        def json(self):
            return {"response": "A generated talk idea.", "done": True}

    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.requests.post", fake_post)
    text = generate("Invent one talk.", max_tokens=220)
    assert text == "A generated talk idea."
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["json"]["model"] == "llama3"
    assert captured["json"]["stream"] is False
    assert captured["json"]["prompt"] == "Invent one talk."
    assert captured["json"]["options"]["num_predict"] == 220


def test_generate_prints_exact_error_when_ollama_rejects(app, monkeypatch, capsys):
    from services.ollama import OllamaError, generate

    class FakeResponse:
        status_code = 404
        text = 'model "llama3" not found'
        reason = "Not Found"

        def json(self):
            raise ValueError("not json")

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.requests.post", lambda *args, **kwargs: FakeResponse())
    try:
        generate("Invent one talk.")
    except OllamaError as exc:
        assert "404" in str(exc)
        assert 'model "llama3" not found' in str(exc)
    else:
        raise AssertionError("expected OllamaError")
    printed = capsys.readouterr().out
    assert "[ollama]" in printed
    assert 'model "llama3" not found' in printed
