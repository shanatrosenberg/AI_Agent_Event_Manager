from flask import Blueprint, jsonify, redirect, render_template, request, session, url_for

from models.speaker import Speaker

from cqrs import (
    LoginCommand,
    RegisterAccountCommand,
    login_handler,
    register_account_handler,
)
from cqrs.errors import DomainError
from services.auth import (
    admin_organizer_username,
    current_user,
    establish_session,
    issue_auth_token,
    safe_next_url,
)

auth_bp = Blueprint("auth", __name__)

PUBLIC_ROLES = ("speaker", "attendee")
ROLE_LABELS = {
    "speaker": "Speaker",
    "attendee": "Attendee",
}


def _wants_json() -> bool:
    if request.is_json:
        return True
    best = request.accept_mimetypes.best_match(["application/json", "text/html"])
    return best == "application/json" and request.accept_mimetypes["application/json"] > (
        request.accept_mimetypes["text/html"] or 0
    )


def _form_values() -> dict[str, str]:
    payload = request.get_json(silent=True) if request.is_json else None
    source = payload if isinstance(payload, dict) else request.form
    return {
        "user_id": str(source.get("user_id") or source.get("username") or "").strip(),
        "password": str(source.get("password") or ""),
        "role": str(source.get("role") or "").strip().lower(),
        "name": str(source.get("name") or "").strip(),
        "next": str(source.get("next") or request.args.get("next") or "").strip(),
    }


def _login_error(message: str, values: dict[str, str], status: int = 401):
    if _wants_json():
        return jsonify({"error": message}), status
    return (
        render_template(
            "login.html",
            error=message,
            username=values.get("user_id", ""),
            next_url=values.get("next", ""),
            admin_username=admin_organizer_username(),
        ),
        status,
    )


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        user = current_user()
        next_url = request.args.get("next")
        if user and user["role"] == "organizer":
            return redirect(safe_next_url(next_url, user["role"]))
        error = None
        if request.args.get("error") == "role":
            error = "Sign in with the Event Organizer admin account to open that dashboard."
        return render_template(
            "login.html",
            error=error,
            username="",
            next_url=next_url or "",
            admin_username=admin_organizer_username(),
        )

    values = _form_values()
    try:
        result = login_handler.handle(
            LoginCommand(
                user_id=values["user_id"],
                password=values["password"],
                role="organizer",
            )
        )
    except DomainError as exc:
        return _login_error(exc.message, values, status=exc.status)

    establish_session(result["user_id"], result["role"], result.get("name"))
    token = issue_auth_token(result["user_id"], result["role"])
    if _wants_json():
        return jsonify({**result, "token": token}), 200
    return redirect(safe_next_url(values.get("next") or "/organizer", result["role"]))


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template(
            "register.html",
            error=None,
            user_id="",
            name="",
            role="speaker",
            roles=PUBLIC_ROLES,
            role_labels=ROLE_LABELS,
        )

    values = _form_values()
    if values["role"] == "organizer":
        if _wants_json():
            return jsonify({"error": "organizer accounts cannot be self-registered"}), 403
        return (
            render_template(
                "register.html",
                error="organizer accounts cannot be self-registered",
                user_id=values["user_id"],
                name=values["name"],
                role="speaker",
                roles=PUBLIC_ROLES,
                role_labels=ROLE_LABELS,
            ),
            403,
        )
    role = values["role"] if values["role"] in PUBLIC_ROLES else "speaker"
    try:
        result = register_account_handler.handle(
            RegisterAccountCommand(
                user_id=values["user_id"],
                password=values["password"],
                role=role,
                name=values["name"],
            )
        )
    except DomainError as exc:
        if _wants_json():
            return jsonify({"error": exc.message}), exc.status
        return (
            render_template(
                "register.html",
                error=exc.message,
                user_id=values["user_id"],
                name=values["name"],
                role=role,
                roles=PUBLIC_ROLES,
                role_labels=ROLE_LABELS,
            ),
            exc.status,
        )

    if _wants_json():
        token = issue_auth_token(result["user_id"], result["role"])
        return jsonify({**result, "token": token}), 201
    if result["role"] == "speaker":
        return redirect(url_for("auth.speaker_login"))
    return redirect(url_for("auth.login"))


@auth_bp.route("/speaker/login", methods=["GET", "POST"])
def speaker_login():
    if request.method == "GET":
        user = current_user()
        next_url = request.args.get("next")
        if user and user["role"] == "speaker":
            return redirect(safe_next_url(next_url, "speaker"))
        error = None
        if request.args.get("error") == "role":
            error = "Sign in with a speaker account to open the speaker portal."
        speakers = Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all()
        return render_template(
            "speaker_login.html",
            error=error,
            username="",
            next_url=next_url or "",
            speakers=speakers,
        )

    values = _form_values()
    try:
        result = login_handler.handle(
            LoginCommand(
                user_id=values["user_id"],
                password=values["password"],
                role="speaker",
            )
        )
    except DomainError as exc:
        if _wants_json():
            return jsonify({"error": exc.message}), exc.status
        return (
            render_template(
                "speaker_login.html",
                error=exc.message,
                username=values.get("user_id", ""),
                next_url=values.get("next", ""),
                speakers=Speaker.query.order_by(Speaker.name.asc(), Speaker.id.asc()).all(),
            ),
            exc.status,
        )

    establish_session(result["user_id"], result["role"], result.get("name"))
    token = issue_auth_token(result["user_id"], result["role"])
    if _wants_json():
        return jsonify({**result, "token": token}), 200
    return redirect(safe_next_url(values.get("next") or "/speaker", result["role"]))


@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    role = session.get("role")
    session.clear()
    if _wants_json():
        return jsonify({"status": "signed_out"}), 200
    if role == "speaker":
        return redirect(url_for("auth.speaker_login"))
    return redirect(url_for("auth.login"))
