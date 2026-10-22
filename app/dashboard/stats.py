"""Berechnet Kennzahlen und Ansichten für ein Dashboard aus einem einzelnen Import.

Bewusst getrennt vom CSV-Import gehalten: neue Auswertungen (siehe REQUIREMENTS.md 3.4)
können hier ergänzt werden, ohne den Importer anzufassen.
"""

from __future__ import annotations

import statistics

from app.dashboard.colorscale import sequential_color
from app.models import ClassDashboard, Import, Student

SONSTIGE = "Sonstige"

GROUP_AHEAD = "vorn"
GROUP_MID = "feld"
GROUP_BEHIND = "hinterher"
GROUP_LABELS = {
    GROUP_AHEAD: "Vorn",
    GROUP_MID: "Im Feld",
    GROUP_BEHIND: "Hinterher",
}
# Ab dieser Klassengröße werden Quartile zur Einstufung genutzt; kleinere Klassen bleiben
# komplett "im Feld", weil die Streuung nichts aussagt.
MIN_STUDENTS_FOR_GROUPS = 4


def _percent(completed: int, total: int) -> float:
    return round(100 * completed / total, 1) if total else 0.0


def _topic_groups(class_dashboard: ClassDashboard, import_: Import):
    """Aktivitäten des Imports (in CSV-Reihenfolge), gruppiert nach Themenbereich
    (Reihenfolge: Topic-Anlage, nicht zugeordnete Aktivitäten zuletzt unter "Sonstige").

    Die Zuordnung läuft über den Aktivitätsnamen und überlebt dadurch jeden Import."""
    topic_of = {a.activity_name: a.topic_id for a in class_dashboard.topic_assignments}
    groups = [
        {
            "id": t.id,
            "name": t.name,
            "activities": [a for a in import_.activities if topic_of.get(a.name) == t.id],
        }
        for t in class_dashboard.topics
    ]
    known = {t.id for t in class_dashboard.topics}
    unassigned = [a for a in import_.activities if topic_of.get(a.name) not in known]
    if unassigned:
        groups.append({"id": None, "name": SONSTIGE, "activities": unassigned})
    return groups


def _classify(percent: float, median: float, q1: float, q3: float, n: int) -> str:
    """Stuft einen Fortschrittswert relativ zur Klasse ein (oberes/unteres Quartil)."""
    if n < MIN_STUDENTS_FOR_GROUPS:
        return GROUP_MID
    if percent >= q3 and percent > median:
        return GROUP_AHEAD
    if percent <= q1 and percent < median:
        return GROUP_BEHIND
    return GROUP_MID


def _class_overview(import_: Import) -> dict:
    """Fortschritt je Schüler:in plus Klassenkennzahlen (Median, Quartile, Einstufung)."""
    per_student: dict[int, dict] = {}
    for rec in import_.records:
        ps = per_student.setdefault(
            rec.student_id,
            {"id": rec.student_id, "name": rec.student.full_name, "completed": 0, "total": 0},
        )
        ps["total"] += 1
        if rec.completed:
            ps["completed"] += 1

    for ps in per_student.values():
        ps["percent"] = _percent(ps["completed"], ps["total"])

    percents = [ps["percent"] for ps in per_student.values()]
    completed_counts = [ps["completed"] for ps in per_student.values()]
    n = len(percents)
    median = round(statistics.median(percents), 1) if percents else 0.0
    median_completed = statistics.median(completed_counts) if completed_counts else 0
    if n >= 2:
        q1, _, q3 = statistics.quantiles(percents, n=4, method="inclusive")
    else:
        q1 = q3 = median

    # Rang 1 = am weitesten. Gleiche Prozentwerte teilen sich den Rang.
    ranked = sorted(percents, reverse=True)
    for ps in per_student.values():
        ps["rank"] = ranked.index(ps["percent"]) + 1
        ps["group"] = _classify(ps["percent"], median, q1, q3, n)
        ps["group_label"] = GROUP_LABELS[ps["group"]]
        ps["gap"] = round(ps["completed"] - median_completed)
        heat_bg, heat_text = sequential_color(ps["percent"])
        ps["heat_bg"], ps["heat_text"] = heat_bg, heat_text

    group_counts = {g: 0 for g in GROUP_LABELS}
    for ps in per_student.values():
        group_counts[ps["group"]] += 1

    return {
        "per_student": per_student,
        "median": median,
        "median_completed": median_completed,
        "q1": round(q1, 1),
        "q3": round(q3, 1),
        "group_counts": group_counts,
        "student_count": n,
    }


def _previous_import(class_dashboard: ClassDashboard, import_: Import) -> Import | None:
    imports = class_dashboard.imports  # absteigend nach Importzeitpunkt
    for i, imp in enumerate(imports):
        if imp.id == import_.id:
            return imports[i + 1] if i + 1 < len(imports) else None
    return None


def _completed_by_name(import_: Import, activity_names: set[str]) -> dict[str, int]:
    """Erledigte Aktivitäten je Schüler:in (über den Namen), nur für die genannten Aktivitäten."""
    counts: dict[str, int] = {}
    for rec in import_.records:
        if rec.activity.name in activity_names:
            name = rec.student.full_name
            counts[name] = counts.get(name, 0) + int(rec.completed)
    return counts


def _deltas(import_: Import, previous: Import | None) -> dict[str, int]:
    """Neu erledigte Aktivitäten seit dem vorherigen Import je Schüler:in (über den Namen).

    Verglichen werden nur Aktivitäten, die in beiden Importen vorkommen, damit hinzugekommene
    oder entfallene Aktivitäten die Veränderung nicht verfälschen."""
    if previous is None:
        return {}
    common = {a.name for a in import_.activities} & {a.name for a in previous.activities}
    now = _completed_by_name(import_, common)
    before = _completed_by_name(previous, common)
    return {name: now.get(name, 0) - count for name, count in before.items()}


def build_stats(class_dashboard: ClassDashboard, import_: Import) -> dict:
    overview = _class_overview(import_)
    per_student = overview["per_student"]

    per_activity_totals: dict[int, dict] = {}
    records_by_key: dict[tuple[int, int], object] = {}
    open_names: dict[int, list[tuple[int, str]]] = {}
    for rec in import_.records:
        pa = per_activity_totals.setdefault(
            rec.activity_id,
            {"completed": 0, "total": 0},
        )
        records_by_key[(rec.student_id, rec.activity_id)] = rec
        pa["total"] += 1
        if rec.completed:
            pa["completed"] += 1
        else:
            open_names.setdefault(rec.activity_id, []).append(
                (rec.student_id, rec.student.full_name)
            )

    total_completed = sum(v["completed"] for v in per_student.values())
    total_possible = sum(v["total"] for v in per_student.values())

    topic_groups = _topic_groups(class_dashboard, import_)

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

    # Veränderung seit dem vorherigen Import (nur sinnvoll, wenn es einen gibt).
    previous = _previous_import(class_dashboard, import_)
    deltas = _deltas(import_, previous)
    for ps in per_student.values():
        ps["delta"] = deltas.get(ps["name"])

    # Rangliste: weitester zuerst, bei Gleichstand alphabetisch.
    ranking = sorted(per_student.values(), key=lambda s: (-s["percent"], s["name"]))
    per_student_by_name = sorted(per_student.values(), key=lambda s: s["name"])

    heatmap_rows = []
    for student in ranking:
        cells = []
        open_count = 0
        for group in topic_groups:
            for activity in group["activities"]:
                rec = records_by_key.get((student["id"], activity.id))
                done = rec.completed if rec else False
                open_count += int(not done)
                cells.append(
                    {
                        "activity_id": activity.id,
                        "completed": done,
                        "completed_at": rec.completed_at if rec else None,
                    }
                )
        heatmap_rows.append(
            {
                "student_id": student["id"],
                "student_name": student["name"],
                "percent": student["percent"],
                "group": student["group"],
                "open_count": open_count,
                "heat_bg": student["heat_bg"],
                "heat_text": student["heat_text"],
                "cells": cells,
            }
        )

    # Offene Aufgaben je Aktivität: wo hängt die Klasse?
    open_activities = []
    for group in topic_groups:
        for activity in group["activities"]:
            students_open = sorted(open_names.get(activity.id, []), key=lambda x: x[1])
            if students_open:
                open_activities.append(
                    {
                        "id": activity.id,
                        "name": activity.name,
                        "topic": group["name"],
                        "open_count": len(students_open),
                        "students": [
                            {"id": sid, "name": name} for sid, name in students_open
                        ],
                    }
                )
    open_activities.sort(key=lambda a: -a["open_count"])

    return {
        "overall_percent": _percent(total_completed, total_possible),
        "total_completed": total_completed,
        "total_possible": total_possible,
        "student_count": overview["student_count"],
        "activity_count": len(per_activity_totals),
        "median": overview["median"],
        "q1": overview["q1"],
        "q3": overview["q3"],
        "group_counts": overview["group_counts"],
        "group_labels": GROUP_LABELS,
        "previous_import_at": previous.imported_at if previous else None,
        "ranking": ranking,
        "per_student": per_student_by_name,
        "per_topic": per_topic,
        "open_activities": open_activities,
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
    overview = _class_overview(import_)
    me = overview["per_student"].get(student.id)

    records_by_activity = {
        rec.activity_id: rec for rec in import_.records if rec.student_id == student.id
    }

    topics = []
    open_list = []
    total_completed = 0
    total_possible = 0
    for group in _topic_groups(class_dashboard, import_):
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
                    "gap": False,
                }
            )
            completed += int(is_completed)

        # Lücke: offen, obwohl später im selben Themenbereich etwas erledigt wurde.
        later_done = False
        for activity in reversed(activities):
            if activity["completed"]:
                later_done = True
            elif later_done:
                activity["gap"] = True

        for activity in activities:
            if not activity["completed"]:
                open_list.append(
                    {"name": activity["name"], "topic": group["name"], "gap": activity["gap"]}
                )

        total = len(activities)
        total_completed += completed
        total_possible += total
        topics.append(
            {
                "name": group["name"],
                "completed": completed,
                "total": total,
                "open": total - completed,
                "percent": _percent(completed, total),
                "activities": activities,
            }
        )

    # Lücken zuerst, dann nach Reihenfolge im Kurs.
    open_list.sort(key=lambda a: not a["gap"])

    previous = _previous_import(class_dashboard, import_)
    delta = _deltas(import_, previous).get(student.full_name)

    return {
        "student_name": student.full_name,
        "completed": total_completed,
        "total": total_possible,
        "open": total_possible - total_completed,
        "percent": _percent(total_completed, total_possible),
        "topics": topics,
        "open_list": open_list,
        "gap_count": sum(1 for a in open_list if a["gap"]),
        "delta": delta,
        "previous_import_at": previous.imported_at if previous else None,
        "class": {
            "median": overview["median"],
            "student_count": overview["student_count"],
            "rank": me["rank"] if me else None,
            "group": me["group"] if me else GROUP_MID,
            "group_label": me["group_label"] if me else GROUP_LABELS[GROUP_MID],
            "gap": me["gap"] if me else 0,
        },
        "students": sorted(
            (
                {"id": s["id"], "name": s["name"], "percent": s["percent"]}
                for s in overview["per_student"].values()
            ),
            key=lambda s: s["name"],
        ),
    }
