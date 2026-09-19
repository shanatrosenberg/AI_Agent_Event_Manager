from pathlib import Path

import click
from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import event, text
from sqlalchemy.engine import Engine

from config import database_uri, sqlalchemy_engine_options
from extensions import db, migrate

DEFAULT_SITE_URL = "http://AiEvents.somee.com"
ENV_FILE = Path(__file__).resolve().parent / ".env"


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
    module = getattr(dbapi_connection, "__class__", type(dbapi_connection)).__module__
    if not module.startswith("sqlite3"):
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(config: dict | None = None) -> Flask:
    load_dotenv(ENV_FILE)
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if config:
        app.config.update(config)

    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    engine_options = sqlalchemy_engine_options(uri)
    if engine_options:
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = engine_options

    db.init_app(app)
    migrate.init_app(app, db)

    import models  # noqa: F401  — register SQLAlchemy models with metadata

    from controllers.attendee import attendee_bp
    from controllers.organizer import organizer_bp
    from controllers.speaker import speaker_bp

    app.register_blueprint(organizer_bp)
    app.register_blueprint(speaker_bp)
    app.register_blueprint(attendee_bp)

    @app.route("/")
    def home():
        return jsonify({
            "message": "Welcome to the Smart Event Management System API",
            "roles_supported": ["Event Organizer", "Speaker", "Attendee"],
            "site": DEFAULT_SITE_URL,
        })

    @app.route("/health")
    def health():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify({"status": "ok", "database": "connected"}), 200
        except Exception as exc:
            return jsonify({
                "status": "error",
                "database": "unavailable",
                "detail": str(exc),
            }), 503

    @app.cli.command("seed")
    @click.option("--reset", is_flag=True, help="Remove previous seed rows, then insert.")
    def seed_command(reset: bool) -> None:
        """Load sample organizers, speakers, attendees, and events."""
        from scripts.seed import seed_database

        click.echo("Seeding database...")
        summary = seed_database(reset=reset)
        for table, count in summary.items():
            click.echo(f"  {table}: {count}")

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
