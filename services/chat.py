"""Two-way in-app chat for program notices and staff replies."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import inspect, text

from extensions import db
from models.chat_message import ChatMessage
from models.event import Event

ATTENDEE_CANCEL_TEMPLATE = (
    'The event "{title}" has been cancelled. '
    "A full refund will be issued for your ticket(s)."
)
SPEAKER_CANCEL_TEMPLATE = 'Your event "{title}" has been cancelled by the organizer.'
ORGANIZER_CANCEL_TEMPLATE = (
    'The lecturer cancelled "{title}". Ticket holders were notified of a full refund.'
)


def ensure_chat_schema() -> None:
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    if "chat_messages" not in tables:
        ChatMessage.__table__.create(bind=db.engine, checkfirst=True)
        return
    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    dialect = db.engine.dialect.name
    column_defs = {
        "read_at": "DATETIME",
        "sender_id": "VARCHAR(64)",
        "sender_role": "VARCHAR(32)",
        "subject": "VARCHAR(255)",
        "parent_id": "VARCHAR(36)",
    }
    added = False
    for name, sql_type in column_defs.items():
        if name in columns:
            continue
        statement = (
            f"ALTER TABLE chat_messages ADD COLUMN {name} {sql_type}"
            if dialect == "sqlite"
            else f"ALTER TABLE chat_messages ADD {name} {sql_type} NULL"
        )
        db.session.execute(text(statement))
        added = True
    if added:
        db.session.commit()


def _as_dict(row: ChatMessage, user_id: str, role: str) -> dict:
    return row.to_dict(viewer_id=user_id, viewer_role=role)


def _thread_root(row: ChatMessage | None) -> ChatMessage | None:
    root = row
    seen = set()
    while root and root.parent_id and root.id not in seen:
        seen.add(root.id)
        parent = db.session.get(ChatMessage, root.parent_id)
        if parent is None:
            break
        root = parent
    return root


def _participates(row: ChatMessage, user_id: str, role: str) -> bool:
    inbound = row.recipient_id == user_id and row.recipient_role == role
    outbound = row.sender_id == user_id and (row.sender_role or "") == role
    return bool(inbound or outbound)


def _counterpart(row: ChatMessage | None, user_id: str, role: str) -> tuple[str, str]:
    if row is None:
        return "", ""
    if role == "organizer":
        if row.sender_role == "speaker" and row.sender_id:
            return row.sender_id, "speaker"
        if row.recipient_role == "speaker" and row.recipient_id:
            return row.recipient_id, "speaker"
    if role == "speaker":
        if row.sender_role == "organizer" and row.sender_id:
            return row.sender_id, "organizer"
        if row.recipient_role == "organizer" and row.recipient_id:
            return row.recipient_id, "organizer"
    return "", ""


def _peer_name(peer_id: str, peer_role: str) -> str:
    user_id = (peer_id or "").strip()
    role = (peer_role or "").strip().lower()
    if role == "speaker" and user_id:
        from models.speaker import Speaker

        speaker = db.session.get(Speaker, user_id)
        name = (speaker.name or "").strip() if speaker is not None else ""
        return name or user_id
    if role == "organizer":
        return "Event Organizer"
    return user_id or "Conversation"


def _staff_messages_with_peer(
    user_id: str, role: str, peer_id: str, peer_role: str
) -> list[ChatMessage]:
    return (
        ChatMessage.query.filter(
            db.or_(
                db.and_(
                    ChatMessage.sender_id == user_id,
                    ChatMessage.sender_role == role,
                    ChatMessage.recipient_id == peer_id,
                    ChatMessage.recipient_role == peer_role,
                ),
                db.and_(
                    ChatMessage.sender_id == peer_id,
                    ChatMessage.sender_role == peer_role,
                    ChatMessage.recipient_id == user_id,
                    ChatMessage.recipient_role == role,
                ),
            )
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def _thread_rows(root: ChatMessage) -> list[ChatMessage]:
    return (
        ChatMessage.query.filter(
            db.or_(ChatMessage.id == root.id, ChatMessage.parent_id == root.id)
        )
        .order_by(ChatMessage.created_at.asc())
        .all()
    )


def list_messages_for(recipient_id: str, recipient_role: str) -> list[dict]:
    user_id = (recipient_id or "").strip()
    role = (recipient_role or "").strip().lower()
    if not user_id or not role:
        return []
    if role in {"speaker", "organizer"}:
        return list_inbox_for(user_id, role)
    rows = (
        ChatMessage.query.filter_by(recipient_id=user_id, recipient_role=role)
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
    return [_as_dict(row, user_id, role) for row in rows]


def list_inbox_for(user_id: str, role: str) -> list[dict]:
    user = (user_id or "").strip()
    viewer_role = (role or "").strip().lower()
    if not user or not viewer_role:
        return []
    rows = (
        ChatMessage.query.filter(
            db.or_(
                db.and_(
                    ChatMessage.recipient_id == user,
                    ChatMessage.recipient_role == viewer_role,
                ),
                db.and_(
                    ChatMessage.sender_id == user,
                    ChatMessage.sender_role == viewer_role,
                ),
            )
        )
        .order_by(ChatMessage.created_at.desc())
        .all()
    )
    if viewer_role == "organizer":
        groups: dict[str, list[ChatMessage]] = {}
        for row in rows:
            if row.recipient_role == "attendee":
                continue
            peer_id, peer_role = _counterpart(row, user, viewer_role)
            if not peer_id or peer_role != "speaker":
                continue
            groups.setdefault(peer_id, []).append(row)
        inbox: list[dict] = []
        for peer_id, items in groups.items():
            items.sort(key=lambda item: item.created_at or 0)
            latest = items[-1]
            unread = any(
                item.recipient_id == user
                and item.recipient_role == viewer_role
                and item.read_at is None
                for item in items
            )
            name = _peer_name(peer_id, "speaker")
            payload = _as_dict(latest, user, viewer_role)
            payload.update(
                {
                    "id": latest.id,
                    "peer_id": peer_id,
                    "peer_role": "speaker",
                    "peer_name": name,
                    "title": name,
                    "subject": name,
                    "body": latest.body,
                    "unread": unread,
                    "read": not unread,
                    "preview_at": latest.created_at.isoformat(sep=" ", timespec="minutes")
                    if latest.created_at
                    else "",
                }
            )
            inbox.append(payload)
        inbox.sort(key=lambda item: item.get("preview_at") or item.get("created_at") or "", reverse=True)
        return inbox
    seen: set[str] = set()
    inbox = []
    for row in rows:
        root = _thread_root(row)
        if root is None or root.id in seen:
            continue
        if root.recipient_role == "attendee":
            continue
        if not _participates(root, user, viewer_role) and not any(
            _participates(item, user, viewer_role) for item in _thread_rows(root)
        ):
            continue
        seen.add(root.id)
        thread = [item for item in _thread_rows(root) if _participates(item, user, viewer_role) or item.id == root.id]
        latest = thread[-1] if thread else root
        unread = any(
            item.recipient_id == user
            and item.recipient_role == viewer_role
            and item.read_at is None
            for item in thread
        )
        payload = _as_dict(root, user, viewer_role)
        payload["body"] = latest.body
        payload["unread"] = unread
        payload["read"] = not unread
        payload["preview_at"] = latest.created_at.isoformat(sep=" ", timespec="minutes") if latest.created_at else ""
        inbox.append(payload)
    inbox.sort(key=lambda item: item.get("preview_at") or item.get("created_at") or "", reverse=True)
    return inbox


def unread_count_for(recipient_id: str, recipient_role: str) -> int:
    user_id = (recipient_id or "").strip()
    role = (recipient_role or "").strip().lower()
    if not user_id or not role:
        return 0
    return ChatMessage.query.filter_by(
        recipient_id=user_id, recipient_role=role, read_at=None
    ).count()


def mark_messages_read(
    recipient_id: str, recipient_role: str, message_id: str | None = None
) -> int:
    from models.chat_message import _utc_now

    user_id = (recipient_id or "").strip()
    role = (recipient_role or "").strip().lower()
    if not user_id or not role:
        return 0
    now = _utc_now()
    if message_id:
        current = db.session.get(ChatMessage, (message_id or "").strip())
        peer_id, peer_role = _counterpart(current, user_id, role)
        if role == "organizer" and peer_id:
            rows = _staff_messages_with_peer(user_id, role, peer_id, peer_role)
        else:
            root = _thread_root(current)
            rows = _thread_rows(root) if root is not None else []
        marked = 0
        for row in rows:
            if row.recipient_id == user_id and row.recipient_role == role and row.read_at is None:
                row.read_at = now
                marked += 1
        return marked
    rows = ChatMessage.query.filter_by(
        recipient_id=user_id, recipient_role=role, read_at=None
    ).all()
    for row in rows:
        row.read_at = now
    return len(rows)


def list_thread(message_id: str, user_id: str, role: str = "speaker") -> list[dict]:
    root_id = (message_id or "").strip()
    user = (user_id or "").strip()
    viewer_role = (role or "").strip().lower() or "speaker"
    if not root_id:
        return []
    current = db.session.get(ChatMessage, root_id)
    root = _thread_root(current)
    if root is None and current is None:
        return []
    peer_id, peer_role = _counterpart(current or root, user, viewer_role)
    if viewer_role == "organizer" and peer_id:
        return [_as_dict(row, user, viewer_role) for row in _staff_messages_with_peer(user, viewer_role, peer_id, peer_role)]
    visible = []
    for row in _thread_rows(root or current):
        if _participates(row, user, viewer_role):
            visible.append(_as_dict(row, user, viewer_role))
    return visible


def send_reply(
    user_id: str,
    role: str,
    body: str,
    *,
    parent_id: str | None = None,
    event_id: str | None = None,
) -> ChatMessage:
    from services.auth import admin_organizer_id

    text_body = " ".join((body or "").split()).strip()
    if len(text_body) < 2:
        raise ValueError("Add a short reply before sending.")
    if len(text_body) > 2000:
        raise ValueError("Reply is too long.")
    sender = (user_id or "").strip()
    sender_role = (role or "").strip().lower()
    if sender_role not in {"speaker", "organizer"}:
        raise ValueError("Only the lecturer and organizer can send chat replies.")
    parent = db.session.get(ChatMessage, (parent_id or "").strip()) if parent_id else None
    if parent_id and parent is None:
        raise ValueError("The original message could not be found.")
    if parent and not _participates(parent, sender, sender_role):
        root = _thread_root(parent)
        if root is None or not _participates(root, sender, sender_role):
            raise ValueError("You can only reply to your own conversation.")
    root = _thread_root(parent) if parent else None
    if sender_role == "speaker":
        recipient_id = admin_organizer_id()
        recipient_role = "organizer"
        kind = "speaker_reply"
    else:
        counterpart = None
        for row in (root, parent):
            if row is None:
                continue
            if row.sender_role == "speaker" and row.sender_id:
                counterpart = row.sender_id
                break
            if row.recipient_role == "speaker" and row.recipient_id:
                counterpart = row.recipient_id
                break
        if not counterpart:
            raise ValueError("Choose a lecturer conversation before sending a reply.")
        recipient_id = counterpart
        recipient_role = "speaker"
        kind = "organizer_reply"
    if sender_role == "organizer":
        subject = _peer_name(recipient_id, recipient_role)
    else:
        subject = _peer_name(sender, "speaker")
    row = ChatMessage(
        id=str(uuid4()),
        recipient_id=recipient_id,
        recipient_role=recipient_role,
        sender_id=sender,
        sender_role=sender_role,
        subject=subject,
        parent_id=root.id if root else None,
        event_id=(event_id or (root.event_id if root else "") or (parent.event_id if parent else "") or "").strip()
        or None,
        kind=kind,
        body=text_body,
    )
    db.session.add(row)
    return row


def send_speaker_reply(
    speaker_id: str,
    body: str,
    *,
    parent_id: str | None = None,
    event_id: str | None = None,
) -> ChatMessage:
    return send_reply(
        speaker_id,
        "speaker",
        body,
        parent_id=parent_id,
        event_id=event_id,
    )


def notify_event_cancelled(
    event: Event,
    *,
    attendee_ids: list[str] | tuple[str, ...],
    speaker_id: str | None,
    cancelled_by: str = "organizer",
) -> dict:
    from services.auth import admin_organizer_id

    title = (event.title or "this event").strip() or "this event"
    actor = (cancelled_by or "organizer").strip().lower()
    created = []
    unique_attendees = []
    seen = set()
    for attendee_id in attendee_ids:
        user_id = (attendee_id or "").strip()
        if not user_id or user_id in seen:
            continue
        seen.add(user_id)
        unique_attendees.append(user_id)
        created.append(
            ChatMessage(
                id=str(uuid4()),
                recipient_id=user_id,
                recipient_role="attendee",
                sender_id=event.organizer_id or admin_organizer_id(),
                sender_role="organizer" if actor != "speaker" else "speaker",
                subject="Event cancelled",
                event_id=event.id,
                kind="event_cancelled",
                body=ATTENDEE_CANCEL_TEMPLATE.format(title=title),
            )
        )
    speaker = (speaker_id or event.speaker_id or "").strip()
    speaker_notified = False
    organizer_notified = False
    if actor != "speaker" and speaker:
        created.append(
            ChatMessage(
                id=str(uuid4()),
                recipient_id=speaker,
                recipient_role="speaker",
                sender_id=event.organizer_id or admin_organizer_id(),
                sender_role="organizer",
                subject="Event cancelled",
                event_id=event.id,
                kind="event_cancelled",
                body=SPEAKER_CANCEL_TEMPLATE.format(title=title),
            )
        )
        speaker_notified = True
    if actor == "speaker":
        created.append(
            ChatMessage(
                id=str(uuid4()),
                recipient_id=admin_organizer_id(),
                recipient_role="organizer",
                sender_id=speaker or event.speaker_id,
                sender_role="speaker",
                subject="Event cancelled",
                event_id=event.id,
                kind="event_cancelled",
                body=ORGANIZER_CANCEL_TEMPLATE.format(title=title),
            )
        )
        organizer_notified = True
    for row in created:
        db.session.add(row)
    return {
        "attendee_count": len(unique_attendees),
        "speaker_notified": speaker_notified,
        "organizer_notified": organizer_notified,
        "message_count": len(created),
    }
