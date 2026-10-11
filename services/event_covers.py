"""Topic-matched Unsplash cover images for event cards."""

from __future__ import annotations

UNSPLASH_CDN = "https://images.unsplash.com"

# Curated Unsplash photos (hotlinkable CDN). Source.unsplash.com is retired.
COVERS: dict[str, tuple[str, ...]] = {
    "ai": (
        "photo-1677442136019-21780ecad995",
        "photo-1620712943543-bcc4688e7485",
        "photo-1535378917048-9e63b66ad58a",
    ),
    "technology": (
        "photo-1518770660439-4636190af475",
        "photo-1517430816045-df4b7de11d1d",
        "photo-1550751827-4bd374c3f58b",
    ),
    "architecture": (
        "photo-1486312338219-ce68d2c6f44d",
        "photo-1497366216548-37526070297c",
        "photo-1503387762-592deb58ef4e",
    ),
    "business": (
        "photo-1556761175-4b46a572b786",
        "photo-1542744173-8e7e53415bb0",
        "photo-1460925895917-afdab827c52f",
    ),
    "workshop": (
        "photo-1552664730-d307ca884978",
        "photo-1524178232363-1fb2b075b655",
        "photo-1531482615713-2afd69097998",
    ),
    "community": (
        "photo-1540575467063-1782f3d4d1c0",
        "photo-1475721027785-f74eccf877e2",
        "photo-1505373877841-8d25f7d46678",
    ),
}

KEYWORD_GROUPS: tuple[tuple[tuple[str, ...], str], ...] = (
    (("ai", "artificial", "llm", "rag", "machine learning", "agent", "neural"), "ai"),
    (("security", "cyber", "zero-trust"), "technology"),
    (("architecture", "cqrs", "flask", "platform", "observability", "engineering"), "architecture"),
    (("business", "product"), "business"),
    (("workshop", "hands-on", "lightning"), "workshop"),
    (("community", "mixer", "ama", "invitation", "food"), "community"),
    (("technology", "tech", "software"), "technology"),
)


def _match_group(text: str) -> str | None:
    blob = (text or "").lower()
    if not blob.strip():
        return None
    for keys, group in KEYWORD_GROUPS:
        if blob == group or blob in keys or any(key in blob for key in keys):
            return group
    return None


def cover_keyword(*parts: str) -> str:
    for part in parts:
        matched = _match_group(part)
        if matched:
            return matched
    return "technology"


def cover_image_url(*parts: str, seed: str = "") -> str:
    group = cover_keyword(*parts)
    photos = COVERS.get(group) or COVERS["technology"]
    token = seed or (parts[0] if parts else group)
    index = sum(ord(ch) for ch in token) % len(photos)
    photo = photos[index]
    return (
        f"{UNSPLASH_CDN}/{photo}"
        f"?auto=format&fit=crop&w=1400&q=70&topic={group}"
    )
