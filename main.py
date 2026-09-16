from flask import Flask, jsonify

from controllers import attendee_bp, organizer_bp, speaker_bp

app = Flask(__name__)
app.register_blueprint(organizer_bp)
app.register_blueprint(speaker_bp)
app.register_blueprint(attendee_bp)

@app.route("/")
def home():
    return jsonify({
        "message": "Welcome to the Smart Event Management System API",
        "roles_supported": ["Event Organizer", "Speaker", "Attendee"]
    })

if __name__ == "__main__":
    app.run(debug=True, port=5000)