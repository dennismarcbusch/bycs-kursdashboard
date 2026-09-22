"""Berechnet Kennzahlen und Ansichten für ein Dashboard aus einem einzelnen Import.

Bewusst getrennt vom CSV-Import gehalten: neue Auswertungen (siehe REQUIREMENTS.md 3.4)
können hier ergänzt werden, ohne den Importer anzufassen.
"""

from __future__ import annotations

from app.dashboard.colorscale import sequential_color
from app.models import ClassDashboard, Import, Student

SONSTIGE = "Sonstige"


def _percent(completed: int, total: int) -> float:
    return round(100 * completed / total, 1) if total else 0.0


def _topic_groups(class_dashboard: ClassDashboard):
    """Aktivitäten der Klasse, gruppiert nach Themenbereich (Reihenfolge: Topic-Anlage,
    nicht zugeordnete Aktivitäten zuletzt unter "Sonstige")."""
    groups = [
        {"id": t.id, "name": t.name, "activities": list(t.activities)}
        for t in class_dashboard.topics
    ]
    unassigned = [a for a in class_dashboard.activities if a.topic_id is None]
    if unassigned:
        groups.append({"id": None, "name": SONSTIGE, "activities": unassigned})
    return groups


def build_stats(class_dashboard: ClassDashboard, import_: Import) -> dict:
    per_student: dict[int, dict] = {}
    per_activity_totals: dict[int, dict] = {}
    records_by_key: dict[tuple[int, int], object] = {}

    for rec in import_.records:
        ps = per_student.setdefault(
            rec.student_id,
            {"id": rec.student_id, "name": rec.student.full_name, "completed": 0, "total": 0},
        )
        pa = per_activity_totals.setdefault(
            rec.activity_id,
            {"topic_id": rec.activity.topic_id, "completed": 0, "total": 0},
        )
        records_by_key[(rec.student_id, rec.activity_id)] = rec

        ps["total"] += 1
        pa["total"] += 1
        if rec.completed:
            ps["completed"] += 1
            pa["completed"] += 1

    total_completed = sum(v["completed"] for v in per_student.values())
    total_possible = sum(v["total"] for v in per_student.values())

    def with_percent(values):
        result = []
        for v in values:
            percent = _percent(v["completed"], v["total"])
            heat_bg, heat_text = sequential_color(percent)
            result.append({**v, "percent": percent, "heat_bg": heat_bg, "heat_text": heat_text})
        return result

    topic_groups = _topic_groups(class_dashboard)

    per_topic = []
    for group in topic_groups:
        completed = sum(
            per_activity_totals.get(a.id, {"completed": 0})["completed"]
            for a in group["activities"]
        )
        total = sum(
            per_activity_totals.get(a.id, {"total": 0})["total"] for a in group["activities"]
        )
        per_topic.append(
            {
                "id": group["id"],
                "name": group["name"],
                "activity_count": len(group["activities"]),
                "completed": completed,
                "total": total,
                "percent": _percent(completed, total),
            }
        )

    per_student_list = sorted(with_percent(per_student.values()), key=lambda x: x["name"])

    heatmap_rows = []
    for student in per_student_list:
        cells = []
        for group in topic_groups:
            for activity in group["activities"]:
                rec = records_by_key.get((student["id"], activity.id))
                cells.append(
                    {
                        "activity_id": activity.id,
                        "completed": rec.completed if rec else False,
                        "completed_at": rec.completed_at if rec else None,
                    }
                )
        heatmap_rows.append(
            {
                "student_id": student["id"],
                "student_name": student["name"],
                "percent": student["percent"],
                "heat_bg": student["heat_bg"],
                "heat_text": student["heat_text"],
                "cells": cells,
            }
        )

    return {
        "overall_percent": _percent(total_completed, total_possible),
        "total_completed": total_completed,
        "total_possible": total_possible,
        "student_count": len(per_student),
        "activity_count": len(per_activity_totals),
        "per_student": per_student_list,
        "per_topic": per_topic,
        "heatmap": {
            "topic_groups": [
                {
                    "id": g["id"],
                    "name": g["name"],
                    "activities": [{"id": a.id, "name": a.name} for a in g["activities"]],
                }
                for g in topic_groups
            ],
            "rows": heatmap_rows,
        },
    }


def build_student_detail(class_dashboard: ClassDashboard, import_: Import, student: Student) -> dict:
    records_by_activity = {
        rec.activity_id: rec for rec in import_.records if rec.student_id == student.id
    }

    topics = []
    total_completed = 0
    total_possible = 0
    for group in _topic_groups(class_dashboard):
        activities = []
        completed = 0
        for activity in group["activities"]:
            rec = records_by_activity.get(activity.id)
            is_completed = bool(rec and rec.completed)
            activities.append(
                {
                    "name": activity.name,
                    "completed": is_completed,
                    "completed_at": rec.completed_at if rec else None,
                }
            )
            completed += int(is_completed)

        total = len(activities)
        total_completed += completed
        total_possible += total
        topics.append(
            {
                "name": group["name"],
                "completed": completed,
                "total": total,
                "percent": _percent(completed, total),
                "activities": activities,
            }
        )

    return {
        "student_name": student.full_name,
        "completed": total_completed,
        "total": total_possible,
        "percent": _percent(total_completed, total_possible),
        "topics": topics,
    }
