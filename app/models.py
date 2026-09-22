from datetime import datetime, timezone

from app.extensions import db


def _utcnow():
    return datetime.now(timezone.utc)


class ClassDashboard(db.Model):
    """Ein Dashboard für genau eine Klasse, verwaltet von genau einer Lehrkraft."""

    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(128), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    # Für V2 (automatischer Abruf): konfigurierbare Export-URL des Aktivitätsabschluss-Berichts.
    export_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    imports = db.relationship(
        "Import",
        backref="class_dashboard",
        cascade="all, delete-orphan",
        order_by="Import.imported_at.desc()",
    )
    students = db.relationship(
        "Student", backref="class_dashboard", cascade="all, delete-orphan"
    )
    activities = db.relationship(
        "Activity", backref="class_dashboard", cascade="all, delete-orphan"
    )
    topics = db.relationship(
        "Topic",
        backref="class_dashboard",
        cascade="all, delete-orphan",
        order_by="Topic.id",
    )


class Import(db.Model):
    """Ein einzelner CSV-Import (manuell hochgeladen oder später automatisch abgerufen)."""

    __tablename__ = "csv_import"

    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    imported_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    source = db.Column(db.String(20), default="upload")  # "upload" | "auto"
    original_filename = db.Column(db.String(300))

    records = db.relationship(
        "CompletionRecord", backref="import_", cascade="all, delete-orphan"
    )


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    full_name = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "class_dashboard_id", "full_name", name="uq_student_per_class"
        ),
    )


class Topic(db.Model):
    """Themenbereich, dem eine Lehrkraft Aktivitäten manuell zuordnet.

    Der Moodle-CSV-Export enthält keine Information über Kursabschnitte - die
    Zuordnung zu Themenbereichen wird daher in der App gepflegt (siehe
    app/dashboard/topics_routes.py) und bleibt über künftige Importe hinweg
    erhalten, da Aktivitäten anhand ihres Namens wiedererkannt werden.
    """

    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)

    activities = db.relationship("Activity", backref="topic", order_by="Activity.id")

    __table_args__ = (
        db.UniqueConstraint("class_dashboard_id", "name", name="uq_topic_per_class"),
    )


class Activity(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    name = db.Column(db.String(300), nullable=False)
    # Kein Themenbereich zugeordnet -> erscheint in der Oberfläche als "Sonstige".
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "class_dashboard_id", "name", name="uq_activity_per_class"
        ),
    )


class CompletionRecord(db.Model):
    """Abschlussstatus einer Aktivität für eine:n Schüler:in innerhalb eines Imports."""

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey("csv_import.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    activity_id = db.Column(db.Integer, db.ForeignKey("activity.id"), nullable=False)
    completed = db.Column(db.Boolean, nullable=False, default=False)
    # Abschlussdatum aus dem CSV-Export, falls vorhanden (nicht bei allen Aktivitäten gesetzt).
    completed_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship("Student")
    activity = db.relationship("Activity")
