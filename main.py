import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, jsonify
from sqlalchemy import event
from sqlalchemy.engine import Engine

from extensions import db, migrate

DEFAULT_DATABASE_URL = "http://my-event-manager.somee.com"


def _database_uri() -> str:
    uri = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    if uri.startswith("postgres://"):
        return uri.replace("postgres://", "postgresql://", 1)

    parsed = urlparse(uri)
    if parsed.scheme in {"http", "https"}:
        host = parsed.hostname or parsed.path.strip("/")
        database = os.environ.get("DATABASE_NAME", "my-event-manager")
        user = os.environ.get("DATABASE_USER", parsed.username or "")
        password = os.environ.get("DATABASE_PASSWORD", parsed.password or "")
        userinfo = ""
        if user:
            userinfo = user
            if password:
                userinfo += f":{password}"
            userinfo += "@"
        return f"mssql+pymssql://{userinfo}{host}/{database}"

    return uri


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
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if config:
        app.config.update(config)

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
        })

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
