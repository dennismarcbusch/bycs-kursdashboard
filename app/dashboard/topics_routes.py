"""Verwaltung der Themenbereiche einer Klasse (siehe app/models.py: Topic).

Getrennt von dashboard/routes.py gehalten, da es sich um einen eigenständigen
Verwaltungsbereich handelt (Themen anlegen/löschen, Aktivitäten zuordnen).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app.auth.decorators import login_required
from app.extensions import db
from app.models import ClassDashboard, Topic

bp = Blueprint("topics", __name__)


def _get_owned_dashboard(dashboard_id: int) -> ClassDashboard:
    cd = db.session.get(ClassDashboard, dashboard_id)
    if cd is None:
        abort(404)
    if cd.owner_username != session["username"]:
        abort(403)
    return cd


@bp.route("/dashboards/<int:dashboard_id>/topics", methods=["GET", "POST"])
@login_required
def manage(dashboard_id):
    cd = _get_owned_dashboard(dashboard_id)

    if request.method == "POST":
        action = request.form.get("action")

        if action == "create_topic":
            name = request.form.get("name", "").strip()
            if not name:
                flash("Bitte einen Namen für den Themenbereich angeben.", "error")
            elif any(t.name == name for t in cd.topics):
                flash(f"Themenbereich '{name}' existiert bereits.", "error")
            else:
                db.session.add(Topic(class_dashboard=cd, name=name))
                db.session.commit()
                flash(f"Themenbereich '{name}' angelegt.", "success")
            return redirect(url_for("topics.manage", dashboard_id=cd.id))

        if action == "assign":
            topic_by_id = {t.id: t for t in cd.topics}
            for activity in cd.activities:
                raw = request.form.get(f"activity-{activity.id}", "")
                activity.topic_id = topic_by_id[int(raw)].id if raw else None
            db.session.commit()
            flash("Zuordnung gespeichert.", "success")
            return redirect(url_for("topics.manage", dashboard_id=cd.id))

    return render_template("dashboard/topics.html", dashboard=cd)


@bp.route("/dashboards/<int:dashboard_id>/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete(dashboard_id, topic_id):
    cd = _get_owned_dashboard(dashboard_id)
    topic = db.session.get(Topic, topic_id)
    if topic is None or topic.class_dashboard_id != cd.id:
        abort(404)

    for activity in topic.activities:
        activity.topic_id = None
    db.session.delete(topic)
    db.session.commit()
    flash(f"Themenbereich '{topic.name}' gelöscht (Aktivitäten sind jetzt 'Sonstige').", "success")
    return redirect(url_for("topics.manage", dashboard_id=cd.id))
