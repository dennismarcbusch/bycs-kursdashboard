from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from app.auth.decorators import (
    accessible_dashboards,
    admin_required,
    current_user,
    get_accessible_dashboard,
    login_required,
)
from app.dashboard.stats import build_stats, build_student_detail
from app.extensions import db
from app.importer.csv_parser import CsvParseError, import_csv
from app.models import ClassDashboard, Student

bp = Blueprint("dashboard", __name__)


@bp.route("/")
@login_required
def list_dashboards():
    return render_template(
        "dashboard/list.html", dashboards=accessible_dashboards(current_user())
    )


@bp.route("/dashboards/<int:dashboard_id>")
@login_required
def detail(dashboard_id):
    cd = get_accessible_dashboard(dashboard_id)
    latest_import = cd.latest_import
    stats = build_stats(cd, latest_import) if latest_import else None
    return render_template(
        "dashboard/detail.html", dashboard=cd, latest_import=latest_import, stats=stats
    )


@bp.route("/dashboards/<int:dashboard_id>/students/<int:student_id>")
@login_required
def student_detail(dashboard_id, student_id):
    cd = get_accessible_dashboard(dashboard_id)
    latest_import = cd.latest_import
    if latest_import is None:
        abort(404)

    student = db.session.get(Student, student_id)
    if student is None or student.import_id != latest_import.id:
        abort(404)

    detail_stats = build_student_detail(cd, latest_import, student)
    return render_template(
        "dashboard/student_detail.html", dashboard=cd, student=student, detail=detail_stats
    )


@bp.route("/dashboards/<int:dashboard_id>/target", methods=["POST"])
@login_required
def set_target(dashboard_id):
    """Setzt oder löscht den manuell gesetzten Soll-Stand (Aktivität, bis zu der die Klasse sein sollte)."""
    cd = get_accessible_dashboard(dashboard_id)
    value = request.form.get("target", "").strip()
    latest = cd.latest_import
    if not value:
        cd.target_activity_name = None
        flash("Soll-Stand entfernt.", "success")
    elif latest is not None and any(a.name == value for a in latest.activities):
        cd.target_activity_name = value
        flash("Soll-Stand gespeichert.", "success")
    else:
        flash("Diese Aktivität gibt es im aktuellen Import nicht.", "error")
    db.session.commit()
    return redirect(url_for("dashboard.detail", dashboard_id=cd.id))


@bp.route("/dashboards/<int:dashboard_id>/upload", methods=["GET", "POST"])
@login_required
def upload(dashboard_id):
    cd = get_accessible_dashboard(dashboard_id)

    if request.method == "POST":
        file = request.files.get("csv_file")
        if not file or file.filename == "":
            flash("Bitte eine CSV-Datei auswählen.", "error")
            return render_template("dashboard/upload.html", dashboard=cd)

        try:
            import_csv(cd, file.stream, original_filename=file.filename)
        except CsvParseError as exc:
            db.session.rollback()
            flash(f"Fehler beim Einlesen der CSV-Datei: {exc}", "error")
            return render_template("dashboard/upload.html", dashboard=cd)

        db.session.commit()
        flash("CSV erfolgreich importiert.", "success")
        return redirect(url_for("dashboard.detail", dashboard_id=cd.id))

    return render_template("dashboard/upload.html", dashboard=cd)


@bp.route("/dashboards/<int:dashboard_id>/delete", methods=["POST"])
@admin_required
def delete(dashboard_id):
    cd = get_accessible_dashboard(dashboard_id)
    db.session.delete(cd)
    db.session.commit()
    flash(f"Klassengruppe '{cd.name}' gelöscht.", "success")
    return redirect(url_for("admin.groups"))
