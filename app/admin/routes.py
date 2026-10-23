"""Admin-Bereich: Benutzerkonten und Klassengruppen anlegen, Benutzer Gruppen zuordnen."""

from __future__ import annotations

import re

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from werkzeug.security import generate_password_hash

from app.auth.decorators import admin_required, current_user
from app.auth.routes import MIN_PASSWORD_LENGTH
from app.extensions import db
from app.models import ClassDashboard, User

bp = Blueprint("admin", __name__, url_prefix="/admin")

_USERNAME = re.compile(r"^[a-z0-9._-]{2,64}$")


def _selected_groups(field: str = "groups") -> list[ClassDashboard]:
    ids = {int(v) for v in request.form.getlist(field) if v.isdigit()}
    return ClassDashboard.query.filter(ClassDashboard.id.in_(ids)).all() if ids else []


@bp.route("/")
@admin_required
def index():
    return redirect(url_for("admin.users"))


@bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        if not _USERNAME.match(username):
            flash("Benutzername: 2-64 Zeichen, nur a-z, 0-9, '.', '_' und '-'.", "error")
        elif not display_name:
            flash("Bitte einen Anzeigenamen angeben.", "error")
        elif len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Das Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen.", "error")
        elif User.query.filter_by(username=username).first():
            flash(f"Der Benutzername '{username}' ist schon vergeben.", "error")
        else:
            user = User(
                username=username,
                display_name=display_name,
                password_hash=generate_password_hash(password),
                is_admin=bool(request.form.get("is_admin")),
            )
            user.classes = _selected_groups()
            db.session.add(user)
            db.session.commit()
            flash(f"Benutzer '{username}' angelegt.", "success")
            return redirect(url_for("admin.users"))

    return render_template(
        "admin/users.html",
        users=User.query.order_by(User.display_name).all(),
        groups=ClassDashboard.query.order_by(ClassDashboard.name).all(),
    )


@bp.route("/users/<int:user_id>", methods=["GET", "POST"])
@admin_required
def edit_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    me = current_user()

    if request.method == "POST":
        display_name = request.form.get("display_name", "").strip()
        password = request.form.get("password", "")
        is_admin = bool(request.form.get("is_admin"))
        is_active = bool(request.form.get("is_active"))
        if not display_name:
            flash("Bitte einen Anzeigenamen angeben.", "error")
        elif password and len(password) < MIN_PASSWORD_LENGTH:
            flash(f"Das Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen.", "error")
        elif user.id == me.id and not (is_admin and is_active):
            flash("Das eigene Konto kann nicht zurückgestuft oder deaktiviert werden.", "error")
        else:
            user.display_name = display_name
            user.is_admin = is_admin
            user.is_active = is_active
            if password:
                user.password_hash = generate_password_hash(password)
            user.classes = _selected_groups()
            db.session.commit()
            flash("Benutzer gespeichert.", "success")
            return redirect(url_for("admin.users"))

    return render_template(
        "admin/user_edit.html",
        user=user,
        groups=ClassDashboard.query.order_by(ClassDashboard.name).all(),
    )


@bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        abort(404)
    if user.id == current_user().id:
        flash("Das eigene Konto kann nicht gelöscht werden.", "error")
        return redirect(url_for("admin.users"))
    db.session.delete(user)
    db.session.commit()
    flash(f"Benutzer '{user.username}' gelöscht.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/groups", methods=["GET", "POST"])
@admin_required
def groups():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Bitte einen Namen für die Klassengruppe angeben.", "error")
        elif ClassDashboard.query.filter_by(name=name).first():
            flash(f"Die Klassengruppe '{name}' existiert bereits.", "error")
        else:
            db.session.add(ClassDashboard(name=name))
            db.session.commit()
            flash(f"Klassengruppe '{name}' angelegt.", "success")
            return redirect(url_for("admin.groups"))

    return render_template(
        "admin/groups.html", groups=ClassDashboard.query.order_by(ClassDashboard.name).all()
    )


@bp.route("/groups/<int:group_id>", methods=["GET", "POST"])
@admin_required
def edit_group(group_id):
    group = db.session.get(ClassDashboard, group_id)
    if group is None:
        abort(404)

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        other = ClassDashboard.query.filter_by(name=name).first()
        if not name:
            flash("Bitte einen Namen angeben.", "error")
        elif other is not None and other.id != group.id:
            flash(f"Die Klassengruppe '{name}' existiert bereits.", "error")
        else:
            group.name = name
            ids = {int(v) for v in request.form.getlist("members") if v.isdigit()}
            group.members = User.query.filter(User.id.in_(ids)).all() if ids else []
            db.session.commit()
            flash("Klassengruppe gespeichert.", "success")
            return redirect(url_for("admin.groups"))

    return render_template(
        "admin/group_edit.html", group=group, users=User.query.order_by(User.display_name).all()
    )


@bp.route("/groups/<int:group_id>/delete", methods=["POST"])
@admin_required
def delete_group(group_id):
    group = db.session.get(ClassDashboard, group_id)
    if group is None:
        abort(404)
    db.session.delete(group)
    db.session.commit()
    flash(f"Klassengruppe '{group.name}' inkl. aller Importe gelöscht.", "success")
    return redirect(url_for("admin.groups"))
