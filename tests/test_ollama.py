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


def test_enhancement_prompt_clips_long_drafts():
    from services.abstract_enhancer import ENHANCE_DRAFT_LIMIT, build_enhancement_prompt

    draft = "CQRS commands and queries. " * 80
    prompt = build_enhancement_prompt(draft)
    assert len(prompt) < len(draft)
    assert len(prompt) <= ENHANCE_DRAFT_LIMIT + 120


def test_clean_enhanced_text_strips_model_preamble():
    from services.abstract_enhancer import _clean_enhanced_text

    cleaned = _clean_enhanced_text(
        'Here is a punchy 2-3 sentence abstract:\n\n"Explore CQRS with Flask for live events."'
    )
    assert cleaned == "Explore CQRS with Flask for live events."


def test_enhancement_prompt_asks_for_a_professional_abstract():
    prompt = build_enhancement_prompt(
        "Hands-on CQRS for event platforms.",
        title="Building CQRS with Flask",
        category="architecture",
    )
    assert prompt.startswith("Write only a punchy 2-3 sentence abstract.")
    assert "2-3 sentence" in prompt
    assert "Hands-on CQRS for event platforms." in prompt
    assert "Abstract:" in prompt
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

    def fake_post(url, json=None, timeout=None, stream=None):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        captured["stream"] = stream
        return FakeResponse()

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.requests.post", fake_post)
    text = generate("Invent one talk.", max_tokens=100, timeout=10, temperature=0.3)
    assert text == "A generated talk idea."
    assert captured["url"] == "http://127.0.0.1:11434/api/generate"
    assert captured["json"]["model"] == "llama3"
    assert captured["json"]["stream"] is False
    assert captured["stream"] is False
    assert captured["json"]["prompt"] == "Invent one talk."
    assert captured["json"]["options"]["num_predict"] == 100
    assert captured["json"]["options"]["temperature"] == 0.3
    assert captured["timeout"] == 10


def test_generate_streams_and_stops_after_two_sentences(app, monkeypatch):
    from services.ollama import generate

    captured = {}
    lines = [
        '{"response":"First sentence. "}',
        '{"response":"Second sentence."}',
        '{"response":" Extra padding that should be ignored.","done":false}',
        '{"response":"","done":true}',
    ]

    class FakeStream:
        status_code = 200
        closed = False

        def iter_lines(self, decode_unicode=True):
            yield from lines

        def close(self):
            self.closed = True

    def fake_post(url, json=None, timeout=None, stream=None):
        captured["json"] = json
        captured["timeout"] = timeout
        captured["stream"] = stream
        return FakeStream()

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.requests.post", fake_post)
    text = generate(
        "Rewrite this.",
        max_tokens=100,
        timeout=10,
        temperature=0.3,
        stream=True,
        keep_alive="30m",
        num_ctx=512,
    )
    assert text == "First sentence. Second sentence."
    assert captured["stream"] is True
    assert captured["json"]["stream"] is True
    assert captured["json"]["keep_alive"] == "30m"
    assert captured["json"]["options"]["num_predict"] == 100
    assert captured["json"]["options"]["temperature"] == 0.3
    assert captured["json"]["options"]["num_ctx"] == 512
    assert captured["timeout"] == (2.0, 10)


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


def test_streamed_generate_stops_at_wall_clock_deadline(app, monkeypatch):
    from services.ollama import generate

    class FakeStream:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield '{"response":"One usable sentence."}'
            yield '{"response":" This would arrive too late."}'

        def close(self):
            return None

    clock = {"calls": 0}

    def fake_monotonic():
        clock["calls"] += 1
        if clock["calls"] <= 3:
            return 100.0 + clock["calls"]
        return 120.0

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.time.monotonic", fake_monotonic)
    monkeypatch.setattr("services.ollama.requests.post", lambda *args, **kwargs: FakeStream())
    text = generate("Rewrite this.", max_tokens=100, timeout=10, stream=True)
    assert text == "One usable sentence."


def test_streamed_generate_keeps_partial_text_if_socket_closes(app, monkeypatch):
    from services.ollama import generate

    class FakeStream:
        status_code = 200

        def iter_lines(self, decode_unicode=True):
            yield '{"response":"A finished conference abstract sentence. "}'
            raise AttributeError("'NoneType' object has no attribute 'read'")

        def close(self):
            return None

    monkeypatch.setenv("OLLAMA_LIVE", "1")
    monkeypatch.setattr("services.ollama.requests.post", lambda *args, **kwargs: FakeStream())
    text = generate("Rewrite this.", max_tokens=100, timeout=10, stream=True)
    assert text == "A finished conference abstract sentence."
