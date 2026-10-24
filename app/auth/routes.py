from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth import throttle
from app.auth.decorators import current_user, log_in, login_required
from app.extensions import db
from app.models import User

bp = Blueprint("auth", __name__)

MIN_PASSWORD_LENGTH = 8

# Wird gegen eine Eingabe geprüft, wenn der Benutzer nicht existiert, damit die Antwortzeit
# nicht verrät, ob ein Benutzername vorhanden ist.
_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def _safe_next(target: str | None) -> str:
    """Nur interne Ziele zulassen (kein Open Redirect).

    Browser lesen "/\\host" wie "//host" und ignorieren Tabs/Zeilenumbrüche, daher sind
    Backslashes und Steuer-/Leerzeichen grundsätzlich ausgeschlossen."""
    if (
        target
        and target.startswith("/")
        and not target.startswith("//")
        and "\\" not in target
        and not any(ord(ch) <= 0x20 or ord(ch) == 0x7F for ch in target)
    ):
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

    log_in(user)
    return redirect(url_for("dashboard.list_dashboards"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        until = throttle.locked_until(username)
        if until is not None:
            flash(
                "Zu viele fehlgeschlagene Anmeldeversuche. Bitte in "
                f"{throttle.minutes_until(until)} Minuten erneut versuchen.",
                "error",
            )
            return _login_page(429)

        user = User.query.filter_by(username=username).first()
        valid = check_password_hash(user.password_hash if user else _DUMMY_HASH, password)
        if user is None or not valid or not user.is_active:
            throttle.register_failure(username)
            flash("Login fehlgeschlagen. Bitte Benutzername und Passwort prüfen.", "error")
            return _login_page()

        throttle.reset(username)
        log_in(user)
        return redirect(_safe_next(request.args.get("next")))

    return _login_page()


def _login_page(status: int = 200):
    return (
        render_template(
            "auth/login.html", dev_login_enabled=current_app.config["DEV_LOGIN_ENABLED"]
        ),
        status,
    )


@bp.route("/logout", methods=["POST"])
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
            log_in(user)  # diese Sitzung bleibt gültig, alle anderen sind damit abgemeldet
            flash("Passwort geändert.", "success")
            return redirect(url_for("dashboard.list_dashboards"))
    return render_template("auth/password.html")
