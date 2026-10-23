from datetime import datetime, timezone

from app.extensions import db
from app.tags import split_tag


def _utcnow():
    return datetime.now(timezone.utc)


class ClassDashboard(db.Model):
    """Ein Dashboard für genau eine Klasse, verwaltet von genau einer Lehrkraft.

    Dauerhaft gespeichert werden nur die Klasse selbst, ihre Themenbereiche und die
    Zuordnung Aktivitätsname -> Themenbereich. Schüler:innen, Aktivitäten und Abschlüsse
    gehören zu einem Import (Schnappschuss) und werden mit jedem Import komplett neu
    aufgebaut; es bleiben nur die letzten Importe erhalten (siehe importer.csv_parser).
    """

    id = db.Column(db.Integer, primary_key=True)
    owner_username = db.Column(db.String(128), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    # Für V2 (Abruf auf Klick): konfigurierbare Export-URL des Aktivitätsabschluss-Berichts.
    export_url = db.Column(db.String(500))
    created_at = db.Column(db.DateTime(timezone=True), default=_utcnow)

    imports = db.relationship(
        "Import",
        backref="class_dashboard",
        cascade="all, delete-orphan",
        order_by="Import.imported_at.desc(), Import.id.desc()",
    )
    topics = db.relationship(
        "Topic",
        backref="class_dashboard",
        cascade="all, delete-orphan",
        order_by="Topic.id",
    )
    topic_assignments = db.relationship(
        "ActivityTopic", backref="class_dashboard", cascade="all, delete-orphan"
    )

    @property
    def latest_import(self):
        return self.imports[0] if self.imports else None


class Import(db.Model):
    """Ein einzelner CSV-Import (Upload oder später Abruf) als in sich geschlossener Stand."""

    __tablename__ = "csv_import"

    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    imported_at = db.Column(db.DateTime(timezone=True), default=_utcnow)
    source = db.Column(db.String(20), default="upload")  # "upload" | "auto"
    original_filename = db.Column(db.String(300))

    students = db.relationship(
        "Student", backref="import_", cascade="all, delete-orphan", order_by="Student.id"
    )
    activities = db.relationship(
        "Activity", backref="import_", cascade="all, delete-orphan", order_by="Activity.position"
    )
    records = db.relationship(
        "CompletionRecord", backref="import_", cascade="all, delete-orphan"
    )


class Student(db.Model):
    """Schüler:in innerhalb eines Imports (identifiziert über den Namen)."""

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey("csv_import.id"), nullable=False)
    full_name = db.Column(db.String(200), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("import_id", "full_name", name="uq_student_per_import"),
    )


class Topic(db.Model):
    """Themenbereich, dem eine Lehrkraft Aktivitäten manuell zuordnet.

    Der Moodle-CSV-Export enthält keine Information über Kursabschnitte - die Zuordnung
    wird daher in der App gepflegt (siehe app/dashboard/topics_routes.py) und über
    ActivityTopic am Aktivitätsnamen festgemacht. Sie überlebt dadurch jeden Import.
    """

    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    name = db.Column(db.String(200), nullable=False)
    # Optionales Hashtag-Kürzel: Aktivitäten mit "#kürzel" am Namensende gehören automatisch
    # zu diesem Themenbereich (Groß-/Kleinschreibung egal), siehe app/tags.py.
    tag = db.Column(db.String(60), nullable=True)

    __table_args__ = (
        db.UniqueConstraint("class_dashboard_id", "name", name="uq_topic_per_class"),
        db.UniqueConstraint("class_dashboard_id", "tag", name="uq_topic_tag_per_class"),
    )


class ActivityTopic(db.Model):
    """Dauerhafte Zuordnung Aktivitätsname -> Themenbereich innerhalb einer Klasse."""

    id = db.Column(db.Integer, primary_key=True)
    class_dashboard_id = db.Column(
        db.Integer, db.ForeignKey("class_dashboard.id"), nullable=False
    )
    activity_name = db.Column(db.String(300), nullable=False)
    topic_id = db.Column(db.Integer, db.ForeignKey("topic.id"), nullable=False)

    __table_args__ = (
        db.UniqueConstraint(
            "class_dashboard_id", "activity_name", name="uq_activity_topic_per_class"
        ),
    )


class Activity(db.Model):
    """Aktivität innerhalb eines Imports; `position` ist die Spaltenreihenfolge der CSV."""

    id = db.Column(db.Integer, primary_key=True)
    import_id = db.Column(db.Integer, db.ForeignKey("csv_import.id"), nullable=False)
    position = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(300), nullable=False)

    __table_args__ = (
        db.UniqueConstraint("import_id", "name", name="uq_activity_per_import"),
    )

    @property
    def display_name(self) -> str:
        """Name ohne Themen-Hashtag."""
        return split_tag(self.name)[0]

    @property
    def tag(self) -> str | None:
        """Themen-Hashtag aus dem Namen (ohne '#') oder None."""
        return split_tag(self.name)[1]


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
