"""Local Ollama text generation for speaker AI helpers."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from typing import Any

import requests

DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
DEFAULT_MODEL = "llama3"


class OllamaError(Exception):
    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message)
        self.status_code = status_code


def _config(name: str, default: str = "") -> str:
    try:
        from flask import current_app

        if current_app:
            value = current_app.config.get(name)
            if value:
                return str(value)
    except RuntimeError:
        pass
    return os.environ.get(name, default)


def _testing() -> bool:
    try:
        from flask import current_app

        return bool(current_app and current_app.config.get("TESTING"))
    except RuntimeError:
        return bool(os.environ.get("PYTEST_CURRENT_TEST"))


def ollama_url() -> str:
    raw = (
        _config("OLLAMA_URL")
        or os.environ.get("OLLAMA_URL")
        or os.environ.get("OLLAMA_HOST")
        or DEFAULT_OLLAMA_URL
    ).strip()
    if not raw:
        raw = DEFAULT_OLLAMA_URL
    cleaned = raw.rstrip("/").replace("://localhost", "://127.0.0.1")
    if cleaned.endswith("/api/generate"):
        return cleaned
    return f"{cleaned}/api/generate"


def _print_failure(message: str, exc: BaseException | None = None) -> None:
    print(f"[ollama] {message}", flush=True)
    if exc is not None:
        print(f"[ollama] {type(exc).__name__}: {exc!s}", flush=True)
    try:
        from flask import current_app

        if current_app:
            current_app.logger.error("%s", message, exc_info=exc)
    except RuntimeError:
        pass


def ollama_model() -> str:
    return (
        _config("OLLAMA_MODEL")
        or os.environ.get("OLLAMA_MODEL")
        or DEFAULT_MODEL
    ).strip() or DEFAULT_MODEL


_SENTENCE_END = re.compile(r"[.!?](?:['\")]*)(?:\s+|$)")


def _has_punchy_abstract(text: str) -> bool:
    """True once the model has produced at least two finished sentences."""
    return len(_SENTENCE_END.findall((text or "").strip())) >= 2


def extract_generated_text(payload: Any, depth: int = 0) -> str:
    """Pull generated text from an Ollama (or similar) JSON payload."""

    if depth > 5 or payload is None:
        return ""
    if isinstance(payload, str):
        text = payload.strip()
        if text[:1] in "[{":
            try:
                parsed = json.loads(text)
            except json.JSONDecodeError:
                return text
            return extract_generated_text(parsed, depth + 1)
        return text
    if isinstance(payload, list):
        for item in payload:
            extracted = extract_generated_text(item, depth + 1)
            if extracted:
                return extracted
        return ""
    if isinstance(payload, dict):
        for key in ("response", "generated_text", "text", "enhanced_abstract", "abstract"):
            if key not in payload or payload[key] in (None, ""):
                continue
            extracted = extract_generated_text(payload[key], depth + 1)
            if extracted:
                return extracted
        return ""
    generated = getattr(payload, "response", None) or getattr(payload, "generated_text", None)
    if generated in (None, ""):
        return ""
    return extract_generated_text(generated, depth + 1)


def generate(
    prompt: str,
    *,
    max_tokens: int = 256,
    timeout: int = 60,
    temperature: float | None = None,
    stream: bool = False,
    keep_alive: str | None = None,
    num_ctx: int | None = None,
) -> str:
    """POST to the local Ollama /api/generate endpoint. Raises OllamaError on failure."""
    if _testing() and (os.environ.get("OLLAMA_LIVE") or "").strip().lower() not in {"1", "true", "yes"}:
        raise OllamaError("Ollama is disabled during tests", status_code=503)

    url = ollama_url()
    model = ollama_model()
    options: dict[str, Any] = {"num_predict": int(max_tokens)}
    if temperature is not None:
        options["temperature"] = float(temperature)
    if num_ctx is not None:
        options["num_ctx"] = int(num_ctx)
    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": bool(stream),
        "options": options,
    }
    if keep_alive:
        payload["keep_alive"] = keep_alive
    deadline = time.monotonic() + max(1.0, float(timeout) - (0.75 if stream else 0.0))
    http_timeout: float | tuple[float, float] = (2.0, float(timeout)) if stream else float(timeout)
    try:
        response = requests.post(url, json=payload, timeout=http_timeout, stream=bool(stream))
    except (requests.RequestException, OSError) as exc:
        _print_failure(f"Ollama request to {url} failed: {exc!s}", exc)
        raise OllamaError(f"Ollama could not be reached: {exc}", status_code=503) from exc

    if response.status_code >= 400:
        detail = (response.text or "").strip() or response.reason
        _print_failure(f"Ollama rejected {url} with HTTP {response.status_code}: {detail}")
        raise OllamaError(
            f"Ollama returned HTTP {response.status_code}: {detail[:280]}",
            status_code=response.status_code,
        )

    if stream:
        return _read_streamed_response(response, url, deadline=deadline)
    return _read_complete_response(response, url)


def _read_complete_response(response: Any, url: str) -> str:
    try:
        payload = response.json()
    except ValueError as exc:
        _print_failure(f"Ollama returned non-JSON from {url}: {response.text!s}", exc)
        raise OllamaError("Ollama did not return JSON", status_code=502) from exc

    text = extract_generated_text(payload)
    if not text:
        _print_failure(f"Ollama returned an empty response from {url}: {payload!r}")
        raise OllamaError("Ollama did not return any generated text", status_code=502)
    return text


def _read_streamed_response(response: Any, url: str, deadline: float) -> str:
    chunks: list[str] = []
    closer = threading.Timer(max(0.1, deadline - time.monotonic()), lambda: _close_response(response))
    closer.daemon = True
    closer.start()
    try:
        for raw in response.iter_lines(decode_unicode=True):
            if time.monotonic() >= deadline:
                break
            if not raw:
                continue
            try:
                data = json.loads(raw)
            except ValueError:
                continue
            piece = data.get("response") or ""
            if piece:
                chunks.append(str(piece))
                if _has_punchy_abstract("".join(chunks)):
                    break
            if data.get("done"):
                break
    except Exception:
        if not chunks:
            raise
    finally:
        closer.cancel()
        _close_response(response)

    text = extract_generated_text("".join(chunks))
    if not text:
        _print_failure(f"Ollama returned an empty stream from {url}")
        raise OllamaError("Ollama did not return any generated text", status_code=502)
    return text


def _close_response(response: Any) -> None:
    close = getattr(response, "close", None)
    if callable(close):
        try:
            close()
        except Exception:
            return


def warm_ollama() -> None:
    """Load llama3 in a daemon thread so Enhance with AI skips the cold-start wait."""
    if _testing():
        return
    thread = threading.Thread(target=_warm_ollama_worker, name="ollama-warm", daemon=True)
    thread.start()


def _warm_ollama_worker() -> None:
    try:
        generate(
            "ok",
            max_tokens=1,
            timeout=90,
            temperature=0.0,
            keep_alive="30m",
            num_ctx=512,
        )
    except Exception as exc:
        _print_failure("Ollama warmup failed", exc)
