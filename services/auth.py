from __future__ import annotations

import os
from datetime import timedelta
from functools import wraps
from typing import Callable, TypeVar

from flask import current_app, redirect, request, session, url_for
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from sqlalchemy import inspect, text
from werkzeug.security import check_password_hash, generate_password_hash

from extensions import db
from models.attendee import Attendee
from models.organizer import Organizer
from models.speaker import Speaker

VALID_ROLES = ("organizer", "speaker", "attendee")
ROLE_MODELS = {
    "organizer": Organizer,
    "speaker": Speaker,
    "attendee": Attendee,
}
AUTH_TOKEN_SALT = "login-token"
AUTH_TOKEN_MAX_AGE = int(timedelta(hours=12).total_seconds())
INVALID_CREDENTIALS = "Invalid username or password"
DEFAULT_ADMIN_ID = "org-admin"
DEFAULT_ADMIN_NAME = "Event Organizer"
DEFAULT_ADMIN_USERNAME = "admin@smartevents.local"
DEFAULT_ADMIN_PASSWORD = "AdminPass!2026"

_F = TypeVar("_F", bound=Callable)
_dummy_hash: str | None = None


def _config_value(name: str, default: str) -> str:
    try:
        configured = current_app.config.get(name)
        if configured:
            return str(configured).strip()
    except RuntimeError:
        pass
    return os.environ.get(name, default).strip() or default


def admin_organizer_id() -> str:
    return _config_value("ORGANIZER_ADMIN_ID", DEFAULT_ADMIN_ID)


def admin_organizer_name() -> str:
    return _config_value("ORGANIZER_ADMIN_NAME", DEFAULT_ADMIN_NAME)


def admin_organizer_username() -> str:
    return _config_value("ORGANIZER_ADMIN_USERNAME", DEFAULT_ADMIN_USERNAME)


def admin_organizer_password() -> str:
    return _config_value("ORGANIZER_ADMIN_PASSWORD", DEFAULT_ADMIN_PASSWORD)


def admin_aliases() -> set[str]:
    username = admin_organizer_username().lower()
    aliases = {
        admin_organizer_id().lower(),
        username,
        username.split("@", 1)[0],
        "admin",
        "organizer",
    }
    return {alias for alias in aliases if alias}


def is_admin_alias(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in admin_aliases()


def dummy_password_hash() -> str:
    """Slow hash used when no account exists, so missing users are not cheaper to probe."""
    global _dummy_hash
    if _dummy_hash is None:
        _dummy_hash = generate_password_hash("invalid-password-placeholder", method="pbkdf2:sha256")
    return _dummy_hash


def verify_password(account, raw_password: str) -> bool:
    stored = getattr(account, "password_hash", None) if account is not None else None
    return check_password_hash(stored or dummy_password_hash(), raw_password)


def get_account(role: str, user_id: str):
    model = ROLE_MODELS.get(role)
    if model is None or not user_id:
        return None
    return db.session.get(model, user_id)


def find_account(role: str, identifier: str):
    """Resolve an account by id, or by speaker display name after login credentials."""
    value = (identifier or "").strip()
    account = get_account(role, value)
    if account is not None or role != "speaker" or not value:
        return account
    return Speaker.query.filter(db.func.lower(Speaker.name) == value.lower()).first()


def create_account(role: str, user_id: str, name: str | None = None):
    model = ROLE_MODELS[role]
    return model(id=user_id, name=name or None)


def issue_auth_token(user_id: str, role: str) -> str:
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=AUTH_TOKEN_SALT)
    return serializer.dumps({"user_id": user_id, "role": role})


def read_auth_token(token: str) -> dict[str, str] | None:
    serializer = URLSafeTimedSerializer(current_app.config["SECRET_KEY"], salt=AUTH_TOKEN_SALT)
    try:
        payload = serializer.loads(token, max_age=AUTH_TOKEN_MAX_AGE)
    except (BadSignature, SignatureExpired, TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    user_id = payload.get("user_id")
    role = payload.get("role")
    if not user_id or role not in VALID_ROLES:
        return None
    return {"user_id": str(user_id), "role": str(role)}


def safe_next_url(value: str | None, role: str | None = None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    if role == "organizer":
        return url_for("organizer_dashboard")
    if role == "speaker":
        return url_for("speaker_dashboard")
    return url_for("home")


def establish_session(user_id: str, role: str, name: str | None) -> None:
    session.clear()
    session["user_id"] = user_id
    session["role"] = role
    session["name"] = name or user_id
    if role == "speaker":
        session["speaker_id"] = user_id
        session["speaker_name"] = name or user_id
    session.permanent = True


def current_user() -> dict[str, str] | None:
    user_id = session.get("user_id")
    role = session.get("role")
    if not user_id or role not in VALID_ROLES:
        return None
    profile = {
        "user_id": user_id,
        "role": role,
        "name": session.get("name") or user_id,
    }
    if role == "speaker":
        profile["speaker_id"] = session.get("speaker_id") or user_id
        profile["speaker_name"] = session.get("speaker_name") or profile["name"]
    return profile


def login_required(*roles: str) -> Callable[[_F], _F]:
    def decorator(view: _F) -> _F:
        @wraps(view)
        def wrapped(*args, **kwargs):
            user = current_user()
            if roles == ("speaker",):
                login_endpoint = "auth.speaker_login"
            elif roles == ("attendee",):
                login_endpoint = "auth.attendee_login"
            else:
                login_endpoint = "auth.login"
            if user is None:
                return redirect(url_for(login_endpoint, next=request.path))
            if roles and user["role"] not in roles:
                return redirect(url_for(login_endpoint, next=request.path, error="role"))
            if "organizer" in roles and not is_admin_alias(user["user_id"]):
                session.clear()
                return redirect(url_for("auth.login", next=request.path, error="role"))
            return view(*args, **kwargs)

        return wrapped  # type: ignore[return-value]

    return decorator


def ensure_admin_organizer() -> Organizer:
    """Create or repair the single dedicated organizer admin account."""
    organizer_id = admin_organizer_id()
    organizer = db.session.get(Organizer, organizer_id)
    if organizer is None:
        organizer = Organizer(id=organizer_id, name=admin_organizer_name())
        organizer.set_password(admin_organizer_password())
        db.session.add(organizer)
        db.session.commit()
        return organizer

    changed = False
    if not organizer.name:
        organizer.name = admin_organizer_name()
        changed = True
    if not organizer.password_hash:
        organizer.set_password(admin_organizer_password())
        changed = True
    if changed:
        db.session.commit()
    return organizer


def ensure_password_hash_columns() -> None:
    """Add password_hash to existing Somee / SQLite tables created before auth existed."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    dialect = db.engine.dialect.name
    for table in ROLE_MODELS.values():
        table_name = table.__tablename__
        if table_name not in tables:
            continue
        columns = {column["name"] for column in inspector.get_columns(table_name)}
        if "password_hash" in columns:
            continue
        if dialect == "sqlite":
            db.session.execute(text(f"ALTER TABLE {table_name} ADD COLUMN password_hash VARCHAR(255)"))
        else:
            db.session.execute(text(f"ALTER TABLE {table_name} ADD password_hash VARCHAR(255) NULL"))
    db.session.commit()


def ensure_event_speaker_column() -> None:
    """Add events.speaker_id on existing Somee / SQLite tables."""
    inspector = inspect(db.engine)
    if "events" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("events")}
    if "speaker_id" in columns:
        return
    dialect = db.engine.dialect.name
    if dialect == "sqlite":
        db.session.execute(text("ALTER TABLE events ADD COLUMN speaker_id VARCHAR(64)"))
    else:
        db.session.execute(text("ALTER TABLE events ADD speaker_id VARCHAR(64) NULL"))
    db.session.commit()


def ensure_event_schedule_columns() -> None:
    """Add start_time and end_time on existing Somee / SQLite event tables."""
    inspector = inspect(db.engine)
    if "events" not in set(inspector.get_table_names()):
        return
    columns = {column["name"] for column in inspector.get_columns("events")}
    dialect = db.engine.dialect.name
    added = False
    for column_name in ("start_time", "end_time"):
        if column_name in columns:
            continue
        if dialect == "sqlite":
            db.session.execute(text(f"ALTER TABLE events ADD COLUMN {column_name} VARCHAR(8)"))
        else:
            db.session.execute(text(f"ALTER TABLE events ADD {column_name} VARCHAR(8) NULL"))
        added = True
    if added:
        db.session.commit()


def ensure_talk_portal_schema() -> None:
    """Add talk-request support on existing Somee / SQLite databases."""
    inspector = inspect(db.engine)
    tables = set(inspector.get_table_names())
    dialect = db.engine.dialect.name
    if "talk_submissions" in tables:
        columns = {column["name"] for column in inspector.get_columns("talk_submissions")}
        added = False
        if "organizer_id" not in columns:
            if dialect == "sqlite":
                db.session.execute(text("ALTER TABLE talk_submissions ADD COLUMN organizer_id VARCHAR(64)"))
            else:
                db.session.execute(text("ALTER TABLE talk_submissions ADD organizer_id VARCHAR(64) NULL"))
            added = True
        column_defs = {
            "date": "VARCHAR(64)",
            "start_time": "VARCHAR(8)",
            "end_time": "VARCHAR(8)",
            "capacity": "INTEGER",
            "event_id": "VARCHAR(36)",
            "rejected_at": "DATETIME",
            "rejection_message": "TEXT",
        }
        for column_name, column_type in column_defs.items():
            if column_name in columns:
                continue
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE talk_submissions ADD COLUMN {column_name} {column_type}"))
            else:
                db.session.execute(text(f"ALTER TABLE talk_submissions ADD {column_name} {column_type} NULL"))
            added = True
        if added:
            db.session.commit()
    if "talk_requests" in tables:
        columns = {column["name"] for column in inspector.get_columns("talk_requests")}
        added = False
        column_defs = {
            "date": "VARCHAR(64)",
            "start_time": "VARCHAR(8)",
            "end_time": "VARCHAR(8)",
            "capacity": "INTEGER",
            "event_id": "VARCHAR(36)",
        }
        for column_name, column_type in column_defs.items():
            if column_name in columns:
                continue
            if dialect == "sqlite":
                db.session.execute(text(f"ALTER TABLE talk_requests ADD COLUMN {column_name} {column_type}"))
            else:
                db.session.execute(text(f"ALTER TABLE talk_requests ADD {column_name} {column_type} NULL"))
            added = True
        if added:
            db.session.commit()
    db.create_all()
