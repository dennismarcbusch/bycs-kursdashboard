"""Verwaltung der Themenbereiche einer Klasse (siehe app/models.py: Topic).

Getrennt von dashboard/routes.py gehalten, da es sich um einen eigenständigen
Verwaltungsbereich handelt (Themen anlegen/löschen, Aktivitäten zuordnen).
"""

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth.decorators import get_accessible_dashboard, login_required
from app.extensions import db
from app.models import ActivityTopic, ClassDashboard, Topic
from app.tags import normalize_tag

bp = Blueprint("topics", __name__)


@bp.route("/dashboards/<int:dashboard_id>/topics", methods=["GET", "POST"])
@login_required
def manage(dashboard_id):
    cd = get_accessible_dashboard(dashboard_id)

    if request.method == "POST":
        action = request.form.get("action")

        if action in ("create_topic", "name_tag"):
            name = request.form.get("name", "").strip()
            raw_tag = request.form.get("tag", "").strip()
            tag = normalize_tag(raw_tag) if raw_tag else None
            if action == "name_tag" and not name:
                name = tag or ""  # ohne eigenen Namen dient das Kürzel als Name
            if not name:
                flash("Bitte einen Namen für den Themenbereich angeben.", "error")
            elif raw_tag and tag is None:
                flash("Das Kürzel darf nur Buchstaben, Ziffern, '-' und '_' enthalten.", "error")
            elif any(t.name == name for t in cd.topics):
                flash(f"Themenbereich '{name}' existiert bereits.", "error")
            elif tag and any((t.tag or "").lower() == tag.lower() for t in cd.topics):
                flash(f"Das Kürzel '#{tag}' ist schon einem Themenbereich zugeordnet.", "error")
            else:
                db.session.add(Topic(class_dashboard=cd, name=name, tag=tag))
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
    topic_counts = {t.id: 0 for t in cd.topics}
    topic_by_tag = {t.tag.lower(): t.id for t in cd.topics if t.tag}
    for activity in activities:
        topic_id = assignment.get(activity.name)
        if topic_id not in topic_counts and activity.tag:
            topic_id = topic_by_tag.get(activity.tag.lower())
        if topic_id in topic_counts:
            topic_counts[topic_id] += 1
    # Im Kurs gefundene Hashtags, für die es noch keinen benannten Themenbereich gibt.
    found_tags = []
    for activity in activities:
        if activity.tag and activity.tag.lower() not in topic_by_tag:
            if activity.tag.lower() not in {t.lower() for t in found_tags}:
                found_tags.append(activity.tag)
    return render_template(
        "dashboard/topics.html",
        dashboard=cd,
        activities=activities,
        assignment=assignment,
        topic_counts=topic_counts,
        found_tags=found_tags,
    )


@bp.route("/dashboards/<int:dashboard_id>/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete(dashboard_id, topic_id):
    cd = get_accessible_dashboard(dashboard_id)
    topic = db.session.get(Topic, topic_id)
    if topic is None or topic.class_dashboard_id != cd.id:
        abort(404)

    ActivityTopic.query.filter_by(topic_id=topic.id).delete()
    db.session.delete(topic)
    db.session.commit()
    flash(f"Themenbereich '{topic.name}' gelöscht (Aktivitäten sind jetzt 'Sonstige').", "success")
    return redirect(url_for("topics.manage", dashboard_id=cd.id))
