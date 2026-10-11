from dataclasses import dataclass

from flask import current_app

from services.ollama import OllamaError, extract_generated_text, generate, ollama_model

DEFAULT_MODEL = "llama3"
ENHANCE_INSTRUCTION = (
    "Act as a professional conference content writer. "
    "Rewrite and expand the following session description into a rich, professional "
    "executive summary/abstract of 3-4 sentences:"
)
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


def build_enhancement_prompt(abstract: str, title: str = "", category: str = "") -> str:
    draft = " ".join((abstract or "").split()).strip()
    lines = [ENHANCE_INSTRUCTION]
    if title.strip():
        lines.append(f"Session title: {title.strip()}")
    if category.strip():
        lines.append(f"Topic: {category.strip()}")
    lines.append("")
    lines.append(draft)
    return "\n".join(lines)


def enhance_abstract(abstract: str, title: str = "", category: str = "") -> EnhancementResult:
    """Send the speaker's draft to local Ollama and return the generated abstract."""
    draft = " ".join((abstract or "").split()).strip()
    prompt = build_enhancement_prompt(draft, title=title, category=category)
    try:
        generated = generate(prompt, max_tokens=400, timeout=120)
    except (OllamaError, OSError) as exc:
        return _unchanged_draft(draft, exc)
    except Exception as exc:
        return _unchanged_draft(draft, exc)

    enhanced = extract_generated_text(generated).strip()
    if not enhanced:
        return _unchanged_draft(draft, ValueError("empty Ollama response"))
    return EnhancementResult(text=enhanced, model=ollama_model())


def _unchanged_draft(draft: str, reason: BaseException) -> EnhancementResult:
    if current_app:
        current_app.logger.warning("Ollama enhance-abstract failed: %s", reason)
    return EnhancementResult(
        text=draft,
        model="local-fallback",
        fallback=True,
        message=FALLBACK_MESSAGE,
    )
