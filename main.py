import os
from datetime import timedelta
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, render_template, session
from sqlalchemy import event
from sqlalchemy.engine import Engine

from extensions import db, migrate
from models.speaker import Speaker
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
)
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


def create_app(config: dict | None = None) -> Flask:
    load_dotenv()
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
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)

    import models  # noqa: F401 — register SQLAlchemy models with metadata

    from controllers.attendee import attendee_bp
    from controllers.auth import auth_bp
    from controllers.organizer import organizer_bp
    from controllers.speaker import speaker_bp, submit_talk_view

    app.register_blueprint(auth_bp)
    app.register_blueprint(organizer_bp)
    app.register_blueprint(speaker_bp)
    app.register_blueprint(attendee_bp)
    app.add_url_rule("/api/submit", "submit_talk_alias", submit_talk_view, methods=["POST"])

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/organizer")
    @login_required("organizer")
    def organizer_dashboard():
        speakers = Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all()
        return render_template(
            "organizer_dashboard.html",
            organizer_id=admin_organizer_id(),
            organizer_name=session.get("name") or admin_organizer_name(),
            organizer_username=admin_organizer_username(),
            speakers=speakers,
            hall_capacities=HALL_CAPACITIES,
            hall_labels=HALL_LABELS,
        )

    @app.route("/approved")
    def approved_events():
        return render_template("approved_events.html")

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

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_password_hash_columns()
        ensure_event_speaker_column()
        ensure_event_schedule_columns()
        ensure_talk_portal_schema()
        ensure_admin_organizer()
    app.run(debug=True, port=5000)