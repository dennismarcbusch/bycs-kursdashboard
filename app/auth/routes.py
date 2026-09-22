from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from app.auth.ldap_auth import authenticate

bp = Blueprint("auth", __name__)


@bp.route("/dev-login")
def dev_login():
    """Login-Umgehung nur für die lokale Entwicklung ohne LDAP-Server (siehe Config.DEV_LOGIN_ENABLED)."""
    if not current_app.config["DEV_LOGIN_ENABLED"]:
        return redirect(url_for("auth.login"))

    session.clear()
    session["username"] = "dev-lehrkraft"
    session["display_name"] = "Dev-Lehrkraft"
    return redirect(url_for("dashboard.list_dashboards"))


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        display_name = authenticate(username, password)
        if display_name is None:
            flash(
                "Login fehlgeschlagen. Bitte Zugangsdaten prüfen - "
                "der Zugang ist außerdem auf die Gruppe 'Lehrer' beschränkt.",
                "error",
            )
            return render_template("auth/login.html")

        session.clear()
        session["username"] = username.strip()
        session["display_name"] = display_name
        return redirect(request.args.get("next") or url_for("dashboard.list_dashboards"))

    return render_template("auth/login.html", dev_login_enabled=current_app.config["DEV_LOGIN_ENABLED"])


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
