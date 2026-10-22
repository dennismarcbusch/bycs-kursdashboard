"""Verwaltung der Themenbereiche einer Klasse (siehe app/models.py: Topic).

Getrennt von dashboard/routes.py gehalten, da es sich um einen eigenständigen
Verwaltungsbereich handelt (Themen anlegen/löschen, Aktivitäten zuordnen).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app.auth.decorators import login_required
from app.extensions import db
from app.models import ActivityTopic, ClassDashboard, Topic

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
            topic_ids = {t.id for t in cd.topics}
            latest = cd.latest_import
            existing = {a.activity_name: a for a in cd.topic_assignments}
            for activity in latest.activities if latest else []:
                raw = request.form.get(f"activity-{activity.id}", "")
                topic_id = int(raw) if raw.isdigit() and int(raw) in topic_ids else None
                current = existing.get(activity.name)
                if topic_id is None:
                    if current is not None:
                        db.session.delete(current)
                elif current is None:
                    db.session.add(
                        ActivityTopic(
                            class_dashboard=cd, activity_name=activity.name, topic_id=topic_id
                        )
                    )
                else:
                    current.topic_id = topic_id
            db.session.commit()
            flash("Zuordnung gespeichert.", "success")
            return redirect(url_for("topics.manage", dashboard_id=cd.id))

    latest = cd.latest_import
    activities = list(latest.activities) if latest else []
    assignment = {a.activity_name: a.topic_id for a in cd.topic_assignments}
    present = {a.name for a in activities}
    topic_counts = {t.id: 0 for t in cd.topics}
    for name, topic_id in assignment.items():
        if name in present and topic_id in topic_counts:
            topic_counts[topic_id] += 1
    return render_template(
        "dashboard/topics.html",
        dashboard=cd,
        activities=activities,
        assignment=assignment,
        topic_counts=topic_counts,
    )


@bp.route("/dashboards/<int:dashboard_id>/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete(dashboard_id, topic_id):
    cd = _get_owned_dashboard(dashboard_id)
    topic = db.session.get(Topic, topic_id)
    if topic is None or topic.class_dashboard_id != cd.id:
        abort(404)

    ActivityTopic.query.filter_by(topic_id=topic.id).delete()
    db.session.delete(topic)
    db.session.commit()
    flash(f"Themenbereich '{topic.name}' gelöscht (Aktivitäten sind jetzt 'Sonstige').", "success")
    return redirect(url_for("topics.manage", dashboard_id=cd.id))
