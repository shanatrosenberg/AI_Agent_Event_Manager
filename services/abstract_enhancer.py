import json
import os
from dataclasses import dataclass

from flask import current_app
from huggingface_hub import InferenceClient
from huggingface_hub.errors import HfHubHTTPError, InferenceTimeoutError, TextGenerationError

DEFAULT_MODEL = "google/flan-t5-large"


def _config(name: str, default: str = "") -> str:
    if current_app:
        value = current_app.config.get(name)
        if value:
            return str(value)
    return os.environ.get(name, default)


def huggingface_token() -> str:
    return (
        (os.getenv("HF_TOKEN") or "").strip()
        or (os.getenv("HUGGINGFACE_API_KEY") or "").strip()
        or _config("HF_TOKEN").strip()
        or _config("HUGGINGFACE_API_KEY").strip()
    )


def local_abstract_enhancement(abstract: str, title: str = "", category: str = "") -> str:
    """Polish a draft on the server when Hugging Face cannot be reached."""
    text = " ".join((abstract or "").split()).strip()
    if not text:
        return ""
    if text[0].islower():
        text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    talk = (title or "").strip()
    topic = (category or "").strip()
    article = "an" if topic[:1].lower() in "aeiou" else "a"
    if talk and topic:
        lead = f"{talk} is {article} {topic} session."
    elif talk:
        lead = f"{talk} is a conference session."
    elif topic:
        lead = f"This is {article} {topic} session."
    else:
        lead = "This conference session covers the following."
    if text.lower().startswith(lead.lower()):
        return text
    return f"{lead} {text}"


def extract_generated_text(payload, depth: int = 0) -> str:
    """Pull the generated abstract out of a Hugging Face inference payload."""
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
        for key in ("generated_text", "text", "enhanced_abstract", "abstract"):
            if key not in payload or payload[key] in (None, ""):
                continue
            extracted = extract_generated_text(payload[key], depth + 1)
            if extracted:
                return extracted
        return ""
    generated = getattr(payload, "generated_text", None)
    if generated in (None, ""):
        return ""
    return extract_generated_text(generated, depth + 1)


FALLBACK_MESSAGE = (
    "Hugging Face could not be reached, so a local rewrite was applied. "
    "Review it before you submit."
)


@dataclass
class EnhancementResult:
    text: str
    model: str
    fallback: bool = False
    message: str = ""
    error: str = ""
    status_code: int = 200


def _model_is_loading(exc: BaseException) -> bool:
    response = getattr(exc, "response", None)
    if getattr(response, "status_code", None) == 503:
        return True
    message = f"{exc} {getattr(exc, 'server_message', '') or ''}".lower()
    return "is loading" in message or "currently loading" in message


def _local_fallback(abstract: str, title: str, category: str, reason: BaseException) -> EnhancementResult:
    current_app.logger.warning("Hugging Face inference unreachable: %s", reason)
    rewritten = local_abstract_enhancement(abstract, title=title, category=category)
    return EnhancementResult(
        text=rewritten,
        model="local-fallback",
        fallback=True,
        message=FALLBACK_MESSAGE,
    )


def enhance_abstract(abstract: str, title: str = "", category: str = "") -> EnhancementResult:
    """Rewrite a talk abstract with the official Hugging Face inference client."""
    token = huggingface_token()
    if not token:
        return EnhancementResult(
            text="",
            model=DEFAULT_MODEL,
            error="Hugging Face is not configured. Set HUGGINGFACE_API_KEY or HF_TOKEN.",
            status_code=503,
        )

    raw_text = " ".join(part for part in (title, category, abstract) if part)
    prompt = f"Rewrite this conference talk abstract into a professional description: {raw_text}"
    try:
        client = InferenceClient(model="google/flan-t5-large", token=os.getenv("HF_TOKEN") or token)
        generated = client.text_generation(prompt, max_new_tokens=256)
    except HfHubHTTPError as exc:
        if _model_is_loading(exc):
            return _local_fallback(abstract, title, category, exc)
        current_app.logger.warning("Hugging Face inference failed: %s", exc)
        return EnhancementResult(text="", model=DEFAULT_MODEL, error=str(exc), status_code=500)
    except TextGenerationError as exc:
        current_app.logger.warning("Hugging Face inference failed: %s", exc)
        return EnhancementResult(text="", model=DEFAULT_MODEL, error=str(exc), status_code=500)
    except (InferenceTimeoutError, OSError) as exc:
        return _local_fallback(abstract, title, category, exc)
    except Exception as exc:
        current_app.logger.exception("Hugging Face inference failed: %s", exc)
        return EnhancementResult(text="", model=DEFAULT_MODEL, error=str(exc), status_code=500)

    enhanced = extract_generated_text(generated)
    if not enhanced:
        return EnhancementResult(
            text="",
            model=DEFAULT_MODEL,
            error="Hugging Face did not return any generated text.",
            status_code=502,
        )
    return EnhancementResult(text=enhanced, model=DEFAULT_MODEL)
