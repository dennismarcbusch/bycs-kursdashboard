from flask import Blueprint, flash, redirect, render_template, request, session, url_for

from app.auth.ldap_auth import authenticate

bp = Blueprint("auth", __name__)


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

    return render_template("auth/login.html")


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
