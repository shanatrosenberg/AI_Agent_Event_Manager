import os

from flask import current_app

DEFAULT_MODEL = "google/flan-t5-large"
HF_INFERENCE_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"


def _config(name: str, default: str = "") -> str:
    if current_app:
        value = current_app.config.get(name)
        if value:
            return str(value)
    return os.environ.get(name, default)


def huggingface_token() -> str:
    return (
        (os.environ.get("HF_TOKEN") or "").strip()
        or (os.environ.get("HUGGINGFACE_API_KEY") or "").strip()
        or _config("HF_TOKEN").strip()
        or _config("HUGGINGFACE_API_KEY").strip()
    )
