from __future__ import annotations

import hashlib
import math
import os
import re
from typing import Iterable

DEFAULT_EMBEDDING_DIM = 384
TOKEN_PATTERN = re.compile(r"[a-z0-9]+")


def embedding_dim() -> int:
    try:
        from flask import current_app

        configured = current_app.config.get("EMBEDDING_DIM")
        if configured:
            return int(configured)
    except (RuntimeError, TypeError, ValueError):
        pass
    return int(os.environ.get("EMBEDDING_DIM", DEFAULT_EMBEDDING_DIM))


def embedding_provider() -> str:
    try:
        from flask import current_app

        configured = current_app.config.get("EMBEDDING_PROVIDER")
        if configured:
            return str(configured).strip().lower()
    except RuntimeError:
        pass
    return (os.environ.get("EMBEDDING_PROVIDER") or "local").strip().lower()


def embedding_model() -> str:
    try:
        from flask import current_app

        configured = current_app.config.get("EMBEDDING_MODEL")
        if configured:
            return str(configured).strip()
    except RuntimeError:
        pass
    return (os.environ.get("EMBEDDING_MODEL") or "local-hash").strip()


def proposal_document(
    title: str = "",
    abstract: str = "",
    category: str = "",
    speaker_name: str = "",
    speaker_bio: str = "",
) -> str:
    parts = [
        f"Title: {title.strip()}" if title else "",
        f"Category: {category.strip()}" if category else "",
        f"Speaker: {speaker_name.strip()}" if speaker_name else "",
        f"Speaker bio: {speaker_bio.strip()}" if speaker_bio else "",
        f"Abstract: {abstract.strip()}" if abstract else "",
    ]
    return "\n".join(part for part in parts if part)


def speaker_document(name: str = "", bio: str = "", talks: Iterable[str] | None = None) -> str:
    talk_text = "\n".join(item.strip() for item in (talks or []) if item and item.strip())
    return proposal_document(title=name, abstract=talk_text, speaker_name=name, speaker_bio=bio)


def tokenize(text: str) -> list[str]:
    tokens = TOKEN_PATTERN.findall((text or "").lower())
    grams = list(tokens)
    grams.extend(f"{left}_{right}" for left, right in zip(tokens, tokens[1:]))
    return grams


def _normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [value / norm for value in vector]


def embed_local(text: str, dim: int | None = None) -> list[float]:
    size = dim or embedding_dim()
    vector = [0.0] * size
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % size
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    return _normalize(vector)


def embed_text(text: str) -> list[float]:
    cleaned = (text or "").strip()
    return embed_local(cleaned)


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    return max(-1.0, min(1.0, sum(a * b for a, b in zip(left, right))))
