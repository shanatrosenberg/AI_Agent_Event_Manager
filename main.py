import os
import sys
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, render_template, request, session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from extensions import db, migrate
from models.speaker import Speaker
from cqrs.store import ensure_event_store_schema
from services.auth import (
    admin_organizer_id,
    admin_organizer_name,
    admin_organizer_username,
    ensure_admin_organizer,
    ensure_event_schedule_columns,
    ensure_event_speaker_column,
    ensure_password_hash_columns,
    ensure_talk_portal_schema,
    login_required,
    current_user,
)
from cqrs import OrganizerStatsQuery, organizer_stats_handler
from services.scheduling import HALL_CAPACITIES, HALL_LABELS

DEFAULT_DATABASE_URL = "http://my-event-manager.somee.com"


def _database_uri() -> str:
    # Check if a direct connection string is provided in the environment
    direct_url = os.environ.get("DATABASE_URL")
    if direct_url:
        return direct_url

    # Fallback to building the connection string for pyodbc using environment variables
    host = os.environ.get("DATABASE_HOST", "AiEventsDB.mssql.somee.com")
    database = os.environ.get("DATABASE_NAME", "AiEventsDB")
    user = os.environ.get("DATABASE_USER", "Avishag10_SQLLogin_1")
    password = os.environ.get("DATABASE_PASSWORD", "Fa388334")
    driver = os.environ.get("DATABASE_ODBC_DRIVER", "ODBC Driver 17 for SQL Server")
    
    # Format the driver name with plus signs for SQLAlchemy compatibility
    driver_encoded = driver.replace(" ", "+")
    
    return f"mssql+pyodbc://{user}:{password}@{host}/{database}?driver={driver_encoded}"


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    module = getattr(dbapi_connection, "__class__", type(dbapi_connection)).__module__
    if not module.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _load_env() -> None:
    here = os.path.dirname(os.path.abspath(__file__))
    load_dotenv(os.path.join(here, ".env"))
    nested_env = os.path.join(here, "AI_Agent_Event_Manager-main", ".env")
    if not os.path.isfile(nested_env):
        return
    from dotenv import dotenv_values

    values = dotenv_values(nested_env)
    for key in ("HF_TOKEN", "HUGGINGFACE_API_KEY", "HUGGINGFACE_MODEL", "TAVILY_API_KEY"):
        value = (values.get(key) or "").strip()
        if value and not (os.environ.get(key) or "").strip():
            os.environ[key] = value


def create_app(config: dict | None = None) -> Flask:
    testing = bool((config or {}).get("TESTING") or "pytest" in sys.modules)
    if not testing:
        _load_env()
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-change-this-secret-key")
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {
        "1",
        "true",
        "yes",
    }
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=12)
    app.config.setdefault("ORGANIZER_ADMIN_ID", os.environ.get("ORGANIZER_ADMIN_ID", "org-admin"))
    app.config.setdefault(
        "ORGANIZER_ADMIN_NAME",
        os.environ.get("ORGANIZER_ADMIN_NAME", "Event Organizer"),
    )
    app.config.setdefault(
        "ORGANIZER_ADMIN_USERNAME",
        os.environ.get("ORGANIZER_ADMIN_USERNAME", "admin@smartevents.local"),
    )
    app.config.setdefault(
        "ORGANIZER_ADMIN_PASSWORD",
        os.environ.get("ORGANIZER_ADMIN_PASSWORD", "AdminPass!2026"),
    )
    if testing:
        app.config.setdefault("HF_TOKEN", "")
        app.config.setdefault("HUGGINGFACE_API_KEY", "")
    else:
        app.config.setdefault("HF_TOKEN", os.environ.get("HF_TOKEN") or "")
        app.config.setdefault(
            "HUGGINGFACE_API_KEY",
            os.environ.get("HUGGINGFACE_API_KEY") or os.environ.get("HF_TOKEN") or "",
        )
    app.config.setdefault(
        "HUGGINGFACE_MODEL",
        os.environ.get("HUGGINGFACE_MODEL", "google/flan-t5-large"),
    )
    if testing:
        app.config.setdefault("EMBEDDING_PROVIDER", "local")
    else:
        app.config.setdefault(
            "EMBEDDING_PROVIDER",
            os.environ.get("EMBEDDING_PROVIDER", "local"),
        )
    app.config.setdefault(
        "EMBEDDING_MODEL",
        os.environ.get("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"),
    )
    app.config.setdefault(
        "EMBEDDING_DIM",
        int(os.environ.get("EMBEDDING_DIM", "384")),
    )
    if testing:
        app.config.setdefault("ASSESSMENT_AGENT_AUTOSTART", False)
        app.config["TAVILY_API_KEY"] = ""
    else:
        app.config.setdefault("TAVILY_API_KEY", os.environ.get("TAVILY_API_KEY") or "")
        app.config.setdefault(
            "ASSESSMENT_AGENT_AUTOSTART",
            os.environ.get("ASSESSMENT_AGENT_AUTOSTART", "1").lower()
            not in {"0", "false", "no"},
        )
    app.config.setdefault(
        "ASSESSMENT_AGENT_INTERVAL",
        int(os.environ.get("ASSESSMENT_AGENT_INTERVAL", "45")),
    )
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)

    import models  # noqa: F401 — register SQLAlchemy models with metadata

    from controllers.attendee import (
        attendee_bp,
        attendee_ticket_cards,
        browse_event_cards,
        browse_filter_options,
        search_browse_event_cards,
    )
    from controllers.auth import auth_bp
    from controllers.organizer import organizer_bp
    from controllers.search import search_bp
    from controllers.speaker import enhance_abstract_view, speaker_bp, submit_talk_view

    app.register_blueprint(auth_bp)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(speaker_bp)
    app.register_blueprint(attendee_bp)
    app.register_blueprint(search_bp)
    app.add_url_rule("/api/submit", "submit_talk_alias", submit_talk_view, methods=["POST"])
    app.add_url_rule(
        "/api/enhance-abstract",
        "enhance_abstract_alias",
        enhance_abstract_view,
        methods=["POST"],
    )

    @app.route("/")
    def home():
        user = current_user()
        attendee_id = user.get("user_id") if user and user.get("role") == "attendee" else ""
        return render_template(
            "index.html",
            attendee_id=attendee_id,
            attendee_name=user.get("name") if user and user.get("role") == "attendee" else "",
        )

    @app.route("/organizer")
    @login_required("organizer")
    def organizer_dashboard():
        speakers = Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all()
        stats = organizer_stats_handler.handle(OrganizerStatsQuery(organizer_id=admin_organizer_id()))
        return render_template(
            "organizer_dashboard.html",
            organizer_id=admin_organizer_id(),
            organizer_name=session.get("name") or admin_organizer_name(),
            organizer_username=admin_organizer_username(),
            speakers=speakers,
            hall_capacities=HALL_CAPACITIES,
            hall_labels=HALL_LABELS,
            kpi_attendees=stats["attendees"],
            kpi_events_held=stats["events_held"],
        )

    @app.route("/approved")
    def approved_events():
        return render_template("approved_events.html")

    @app.route("/events")
    @app.route("/browse")
    def browse_events():
        user = current_user()
        attendee_id = user.get("user_id") if user and user.get("role") == "attendee" else ""
        search_query = (request.args.get("q") or request.args.get("query") or "").strip()
        topic = (request.args.get("topic") or request.args.get("category") or "").strip()
        speaker = (request.args.get("speaker") or request.args.get("speaker_id") or "").strip()
        all_events = browse_event_cards()
        if search_query:
            events = search_browse_event_cards(
                search_query,
                topic=topic or None,
                speaker=speaker or None,
            )
        elif topic or speaker:
            events = browse_event_cards(topic=topic or None, speaker=speaker or None)
        else:
            events = all_events
        return render_template(
            "browse_events.html",
            events=events,
            all_events=all_events,
            filter_options=browse_filter_options(all_events),
            search_query=search_query,
            selected_topic=topic,
            selected_speaker=speaker,
            attendee_id=attendee_id,
            attendee_name=user.get("name") if user and user.get("role") == "attendee" else "",
        )

    @app.route("/my-events")
    @app.route("/my-tickets")
    @login_required("attendee")
    def my_tickets():
        user = current_user()
        attendee_id = user.get("user_id") if user else ""
        return render_template(
            "my_tickets.html",
            tickets=attendee_ticket_cards(attendee_id),
            attendee_id=attendee_id,
            attendee_name=user.get("name") if user else "",
        )

    @app.route("/speaker")
    @login_required("speaker")
    def speaker_dashboard():
        return render_template(
            "speaker_dashboard.html",
            speaker_id=session.get("speaker_id") or session.get("user_id"),
            speaker_name=session.get("speaker_name") or session.get("name") or session.get("user_id"),
            hall_capacities=HALL_CAPACITIES,
            hall_labels=HALL_LABELS,
        )

    from services.deep_agent import start_assessment_agent

    start_assessment_agent(app)
    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_password_hash_columns()
        ensure_event_speaker_column()
        ensure_event_schedule_columns()
        ensure_talk_portal_schema()
        ensure_event_store_schema()
        ensure_admin_organizer()
    app.run(debug=True, port=5000)