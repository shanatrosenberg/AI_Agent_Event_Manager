from flask import Flask, jsonify

from config import Config
from controllers.attendee import attendee_bp
from controllers.organizer import organizer_bp
from controllers.speaker import speaker_bp
from extensions import db, migrate
import models  # noqa: F401  # register models with SQLAlchemy / Flask-Migrate


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db)

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
