from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.decorators import current_user, login_required
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8

# Wird gegen eine Eingabe geprüft, wenn der Benutzer nicht existiert, damit die Antwortzeit
# nicht verrät, ob ein Benutzername vorhanden ist.
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def _safe_next(target: str | None) -> str:
    """Nur interne Ziele zulassen (kein Open Redirect)."""
    if target and target.startswith("/") and not target.startswith("//"):
        return target
    return url_for("dashboard.list_dashboards")


@bp.route("/dev-login")
def dev_login():
    """Login-Umgehung nur für die lokale Entwicklung (siehe Config.DEV_LOGIN_ENABLED).

    Meldet als lokalen Admin 'dev-admin' an (wird bei Bedarf angelegt)."""
    if not current_app.config["DEV_LOGIN_ENABLED"]:
        return redirect(url_for("auth.login"))

    user = User.query.filter_by(username="dev-admin").first()
    if user is None:
        user = User(
            username="dev-admin",
            display_name="Dev-Admin",
            password_hash=generate_password_hash("dev-admin-unused"),
            is_admin=True,
        )
        db.session.add(user)
        db.session.commit()

    session.clear()
    session["user_id"] = user.id
    return redirect(url_for("dashboard.list_dashboards"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
        if user is None or not valid or not user.is_active:
            flash("Login fehlgeschlagen. Bitte Benutzername und Passwort prüfen.", "error")
            return render_template(
                "auth/login.html", dev_login_enabled=current_app.config["DEV_LOGIN_ENABLED"]
            )

        session.clear()
        session["user_id"] = user.id
        return redirect(_safe_next(request.args.get("next")))

    return render_template(
        "auth/login.html", dev_login_enabled=current_app.config["DEV_LOGIN_ENABLED"]
    )


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@bp.route("/account/password", methods=["GET", "POST"])
@login_required
def change_password():
    user = current_user()
    if request.method == "POST":
        old = request.form.get("old_password", "")
        new = request.form.get("new_password", "")
        repeat = request.form.get("repeat_password", "")
        if not check_password_hash(user.password_hash, old):
            flash("Das aktuelle Passwort stimmt nicht.", "error")
        elif len(new) < MIN_PASSWORD_LENGTH:
            flash(f"Das neue Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen.", "error")
        elif new != repeat:
            flash("Die beiden neuen Passwörter stimmen nicht überein.", "error")
        else:
            user.password_hash = generate_password_hash(new)
            db.session.commit()
            flash("Passwort geändert.", "success")
            return redirect(url_for("dashboard.list_dashboards"))
    return render_template("auth/password.html")
