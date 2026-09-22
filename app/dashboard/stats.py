"""Berechnet Kennzahlen für ein Dashboard aus einem einzelnen Import.

Bewusst getrennt vom CSV-Import gehalten: neue Auswertungen (siehe REQUIREMENTS.md 3.4)
können hier ergänzt werden, ohne den Importer anzufassen.
"""

from __future__ import annotations

from app.models import Import


def _percent(completed: int, total: int) -> float:
    return round(100 * completed / total, 1) if total else 0.0


def build_stats(import_: Import) -> dict:
    per_student: dict[int, dict] = {}
    per_activity: dict[int, dict] = {}

    for rec in import_.records:
        ps = per_student.setdefault(
            rec.student_id, {"name": rec.student.full_name, "completed": 0, "total": 0}
        )
        pa = per_activity.setdefault(
            rec.activity_id, {"name": rec.activity.name, "completed": 0, "total": 0}
        )
        ps["total"] += 1
        pa["total"] += 1
        if rec.completed:
            ps["completed"] += 1
            pa["completed"] += 1

    total_completed = sum(v["completed"] for v in per_student.values())
    total_possible = sum(v["total"] for v in per_student.values())

    def with_percent(values):
        return [
            {**v, "percent": _percent(v["completed"], v["total"])} for v in values
        ]

    return {
        "overall_percent": _percent(total_completed, total_possible),
        "total_completed": total_completed,
        "total_possible": total_possible,
        "student_count": len(per_student),
        "activity_count": len(per_activity),
        "per_student": sorted(with_percent(per_student.values()), key=lambda x: x["name"]),
        "per_activity": sorted(with_percent(per_activity.values()), key=lambda x: x["name"]),
    }
