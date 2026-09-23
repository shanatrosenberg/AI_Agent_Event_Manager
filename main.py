import os
from urllib.parse import urlparse

from dotenv import load_dotenv
from flask import Flask, render_template
from sqlalchemy import event
from sqlalchemy.engine import Engine

from extensions import db, migrate

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
    app.config["SQLALCHEMY_DATABASE_URI"] = _database_uri()
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)

    import models  # noqa: F401 — register SQLAlchemy models with metadata

    from controllers.attendee import attendee_bp
    from controllers.organizer import organizer_bp
    from controllers.speaker import speaker_bp

    app.register_register_blueprint = organizer_bp  # keeping existing setup logic
    app.register_blueprint(organizer_bp)
    app.register_blueprint(speaker_bp)
    app.register_blueprint(attendee_bp)

    @app.route("/")
    def home():
        return render_template("index.html")

    @app.route("/organizer")
    def organizer_dashboard():
        return render_template("organizer_dashboard.html")

    return app


app = create_app()


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)