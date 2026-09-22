from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from app.auth.decorators import login_required
from app.dashboard.stats import build_stats, build_student_detail
from app.extensions import db
from app.importer.csv_parser import CsvParseError, import_csv
from app.models import Activity, ClassDashboard, Student, Topic

bp = Blueprint("dashboard", __name__)


def _get_owned_dashboard(dashboard_id: int) -> ClassDashboard:
    cd = db.session.get(ClassDashboard, dashboard_id)
    if cd is None:
        abort(404)
    if cd.owner_username != session["username"]:
        abort(403)
    return cd


@bp.route("/")
@login_required
def list_dashboards():
    dashboards = (
        ClassDashboard.query.filter_by(owner_username=session["username"])
        .order_by(ClassDashboard.name)
        .all()
    )
    return render_template("dashboard/list.html", dashboards=dashboards)


@bp.route("/dashboards/new", methods=["GET", "POST"])
@login_required
def new_dashboard():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Bitte einen Namen für die Klasse angeben.", "error")
            return render_template("dashboard/new.html")

        cd = ClassDashboard(owner_username=session["username"], name=name)
        db.session.add(cd)
        db.session.commit()
        flash(f"Klasse '{cd.name}' angelegt.", "success")
        return redirect(url_for("dashboard.upload", dashboard_id=cd.id))

    return render_template("dashboard/new.html")


@bp.route("/dashboards/<int:dashboard_id>")
@login_required
def detail(dashboard_id):
    cd = _get_owned_dashboard(dashboard_id)
    latest_import = cd.imports[0] if cd.imports else None
    stats = build_stats(cd, latest_import) if latest_import else None
    return render_template(
        "dashboard/detail.html", dashboard=cd, latest_import=latest_import, stats=stats
    )


@bp.route("/dashboards/<int:dashboard_id>/students/<int:student_id>")
@login_required
def student_detail(dashboard_id, student_id):
    cd = _get_owned_dashboard(dashboard_id)
    student = db.session.get(Student, student_id)
    if student is None or student.class_dashboard_id != cd.id:
        abort(404)

    latest_import = cd.imports[0] if cd.imports else None
    if latest_import is None:
        abort(404)

    detail_stats = build_student_detail(cd, latest_import, student)
    return render_template(
        "dashboard/student_detail.html", dashboard=cd, student=student, detail=detail_stats
    )


@bp.route("/dashboards/<int:dashboard_id>/upload", methods=["GET", "POST"])
@login_required
def upload(dashboard_id):
    cd = _get_owned_dashboard(dashboard_id)

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
@login_required
def delete(dashboard_id):
    cd = _get_owned_dashboard(dashboard_id)
    db.session.delete(cd)
    db.session.commit()
    flash(f"Klasse '{cd.name}' gelöscht.", "success")
    return redirect(url_for("dashboard.list_dashboards"))
