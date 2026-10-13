from dataclasses import dataclass

from flask import current_app

from services.ollama import OllamaError, extract_generated_text, generate, ollama_model

DEFAULT_MODEL = "llama3"
ENHANCE_MAX_TOKENS = 100
ENHANCE_TIMEOUT_SECONDS = 9
ENHANCE_TEMPERATURE = 0.3
ENHANCE_NUM_CTX = 512
ENHANCE_KEEP_ALIVE = "30m"
ENHANCE_DRAFT_LIMIT = 480
ENHANCE_INSTRUCTION = "Write only a punchy 2-3 sentence abstract. No intro, title, or labels."
FALLBACK_MESSAGE = (
    "Ollama could not be reached, so your original draft was left unchanged. "
    "Start Ollama and try Enhance with AI again."
)


@dataclass
class EnhancementResult:
    text: str
    model: str
    fallback: bool = False
    message: str = ""
    error: str = ""
    status_code: int = 200


def _compact_draft(abstract: str) -> str:
    draft = " ".join((abstract or "").split()).strip()
    if len(draft) <= ENHANCE_DRAFT_LIMIT:
        return draft
    clipped = draft[:ENHANCE_DRAFT_LIMIT].rsplit(" ", 1)[0].strip()
    return clipped or draft[:ENHANCE_DRAFT_LIMIT]


def build_enhancement_prompt(abstract: str, title: str = "", category: str = "") -> str:
    draft = _compact_draft(abstract)
    parts = [ENHANCE_INSTRUCTION]
    title = title.strip()
    topic = category.strip()
    if title:
        parts.append(f"Title: {title}")
    if topic:
        parts.append(f"Topic: {topic}")
    parts.append(f"Draft: {draft}")
    parts.append("Abstract:")
    return "\n".join(parts)


def enhance_abstract(abstract: str, title: str = "", category: str = "") -> EnhancementResult:
    """Send the speaker's draft to local Ollama and return a short abstract."""
    draft = " ".join((abstract or "").split()).strip()
    prompt = build_enhancement_prompt(draft, title=title, category=category)
    try:
        generated = generate(
            prompt,
            max_tokens=ENHANCE_MAX_TOKENS,
            timeout=ENHANCE_TIMEOUT_SECONDS,
            temperature=ENHANCE_TEMPERATURE,
            stream=True,
            keep_alive=ENHANCE_KEEP_ALIVE,
            num_ctx=ENHANCE_NUM_CTX,
        )
    except (OllamaError, OSError) as exc:
        return _unchanged_draft(draft, exc)
    except Exception as exc:
        return _unchanged_draft(draft, exc)

    enhanced = _clean_enhanced_text(extract_generated_text(generated))
    if not enhanced:
        return _unchanged_draft(draft, ValueError("empty Ollama response"))
    return EnhancementResult(text=enhanced, model=ollama_model())


_PREAMBLE = (
    "here is a punchy 2-3 sentence abstract",
    "here's a punchy 2-3 sentence abstract",
    "here is a rewritten abstract",
    "here's a rewritten abstract",
    "here is a rewritten version",
    "here's a rewritten version",
)


def _clean_enhanced_text(text: str) -> str:
    cleaned = " ".join((text or "").split()).strip().strip('"').strip()
    lower = cleaned.lower()
    for prefix in _PREAMBLE:
        if lower.startswith(prefix):
            cleaned = cleaned[len(prefix):].lstrip(" :-\n")
            break
    return cleaned.strip().strip('"').strip()


def _unchanged_draft(draft: str, reason: BaseException) -> EnhancementResult:
    if current_app:
        current_app.logger.warning("Ollama enhance-abstract failed: %s", reason)
    return EnhancementResult(
        text=draft,
        model="local-fallback",
        fallback=True,
        message=FALLBACK_MESSAGE,
    )
