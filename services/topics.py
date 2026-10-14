from __future__ import annotations

import re

from sqlalchemy import func, inspect

from extensions import db
from models.topic import Topic

DEFAULT_TOPICS = (
    ("ai", "AI"),
    ("architecture", "Architecture"),
    ("community", "Community"),
    ("product", "Product"),
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def topic_slug(value: str) -> str:
    cleaned = _SLUG_RE.sub("-", (value or "").strip().lower()).strip("-")
    return cleaned[:128]


def topic_name(value: str) -> str:
    return " ".join((value or "").split()).strip()[:128]


def _topics_table_exists() -> bool:
    return "topics" in set(inspect(db.engine).get_table_names())


def _create_topics_table() -> None:
    if _topics_table_exists():
        return
    Topic.__table__.create(db.engine)
    db.session.commit()


def _existing_topic(slug: str, name: str) -> Topic | None:
    return Topic.query.filter(
        (func.lower(Topic.slug) == slug) | (func.lower(Topic.name) == name.lower())
    ).first()


def _insert_topic(slug: str, name: str) -> Topic | None:
    if not slug or slug in {"other", "other-"}:
        return None
    found = _existing_topic(slug, name)
    if found:
        return found
    topic = Topic(slug=slug, name=name)
    db.session.add(topic)
    return topic


def ensure_topics_schema() -> None:
    _create_topics_table()
    for slug, name in DEFAULT_TOPICS:
        _insert_topic(slug, name)
    db.session.commit()


def upsert_topic(value: str, commit: bool = True) -> Topic | None:
    name = topic_name(value)
    slug = topic_slug(name)
    if not slug or slug in {"other", "other-"}:
        return None
    _create_topics_table()
    topic = _insert_topic(slug, name)
    if commit:
        db.session.commit()
    return topic


def list_topics() -> list[Topic]:
    ensure_topics_schema()
    return Topic.query.order_by(func.lower(Topic.name).asc()).all()


def list_topic_payloads() -> list[dict[str, str]]:
    return [item.to_dict() for item in list_topics()]


def delete_topic(slug: str) -> bool:
    key = topic_slug(slug)
    if not key:
        return False
    topic = Topic.query.filter(func.lower(Topic.slug) == key).first()
    if topic is None:
        return False
    db.session.delete(topic)
    db.session.commit()
    return True


def catalog_topic_labels() -> list[str]:
    labels = []
    seen = set()
    for item in list_topics():
        label = item.name or item.slug
        key = label.lower()
        if key in seen:
            continue
        seen.add(key)
        labels.append(label)
    return labels
