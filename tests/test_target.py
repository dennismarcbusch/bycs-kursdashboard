import io

from app.dashboard.stats import build_stats, build_student_detail
from app.extensions import db
from app.importer.csv_parser import import_csv
from app.models import ClassDashboard

from conftest import login, make_user

# Aktivitäten in Kursreihenfolge: A B C D E F (je 6)
CSV = """,E-Mail-Adresse,Institution,A #t1,B #t1,C #t2,D #t2,E #t3,F #t3
Voll,x,1,Abgeschlossen,Abgeschlossen,Abgeschlossen,Abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen
Fast,x,1,Abgeschlossen,Abgeschlossen,Abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen
Luecke,x,1,Abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Abgeschlossen,Abgeschlossen
Wenig,x,1,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen
"""


def _class(target=None):
    cd = ClassDashboard(name="Test", target_activity_name=target)
    db.session.add(cd)
    import_csv(cd, io.StringIO(CSV))
    db.session.commit()
    return cd


def _by_name(stats):
    return {s["name"]: s for s in stats["ranking"]}


def test_without_target_nothing_is_due(app):
    cd = _class()
    stats = build_stats(cd, cd.latest_import)
    assert stats["target"]["set"] is False
    assert all(s["due"] is None for s in stats["ranking"])
    assert all(not c["due"] for row in stats["heatmap"]["rows"] for c in row["cells"])


def test_target_classifies_by_soll_fulfilment(app):
    cd = _class(target="D #t2")  # Soll = A, B, C, D
    stats = build_stats(cd, cd.latest_import)
    by = _by_name(stats)

    assert stats["target"]["due_total"] == 4
    assert stats["target"]["percent_of_all"] == round(100 * 4 / 6, 1)
    assert by["Voll"]["group"] == "vorn" and by["Voll"]["due"] == 0
    assert by["Fast"]["group"] == "feld" and by["Fast"]["due"] == 1  # 3 von 4 = 75 %
    assert by["Luecke"]["group"] == "hinterher" and by["Luecke"]["due"] == 3  # 1 von 4
    assert by["Wenig"]["group"] == "hinterher" and by["Wenig"]["due"] == 4


def test_target_marks_due_cells_and_open_activities(app):
    cd = _class(target="D #t2")
    stats = build_stats(cd, cd.latest_import)

    wenig = next(r for r in stats["heatmap"]["rows"] if r["student_name"] == "Wenig")
    assert [c["due"] for c in wenig["cells"]] == [True, True, True, True, False, False]

    open_names = [(a["name"], a["due"]) for a in stats["open_activities"]]
    due_first = [n for n, due in open_names if due]
    assert open_names[: len(due_first)] == [(n, True) for n in due_first]  # fällige zuerst
    assert {n for n, due in open_names if not due} == {"E", "F"}


def test_target_student_detail_lists_due_first(app):
    cd = _class(target="D #t2")
    student = next(s for s in cd.latest_import.students if s.full_name == "Luecke")
    detail = build_student_detail(cd, cd.latest_import, student)

    assert detail["due_count"] == 3
    assert [(a["name"], a["due"]) for a in detail["open_list"]] == [
        ("B", True),
        ("C", True),
        ("D", True),
    ]
    assert detail["target"] == {"set": True, "missing": False, "label": "D"}


def test_missing_target_is_ignored(app):
    cd = _class(target="Gibt es nicht #x")
    stats = build_stats(cd, cd.latest_import)
    assert stats["target"]["set"] and stats["target"]["missing"]
    assert all(s["due"] is None for s in stats["ranking"])
    assert {s["group"] for s in stats["ranking"]} <= {"vorn", "feld", "hinterher"}


def test_target_options_cover_topic_ends_and_activities(app):
    cd = _class()
    stats = build_stats(cd, cd.latest_import)
    assert [(o["label"], o["value"]) for o in stats["target"]["choices"]] == [
        ("Ende von: t1", "B #t1"),
        ("Ende von: t2", "D #t2"),
        ("Ende von: t3", "F #t3"),
    ]
    assert len(stats["target"]["singles"]) == 6
    assert stats["target"]["singles"][0]["label"].startswith("1. A (t1)")


def test_set_target_route(app, client):
    cd = _class()
    make_user("lehrer", groups=[cd])
    login(client, "lehrer")

    client.post(f"/dashboards/{cd.id}/target", data={"target": "D #t2"})
    db.session.refresh(cd)
    assert cd.target_activity_name == "D #t2"

    client.post(f"/dashboards/{cd.id}/target", data={"target": "unbekannt"})
    db.session.refresh(cd)
    assert cd.target_activity_name == "D #t2"  # ungültige Eingabe ändert nichts

    client.post(f"/dashboards/{cd.id}/target", data={"target": ""})
    db.session.refresh(cd)
    assert cd.target_activity_name is None

    page = client.get(f"/dashboards/{cd.id}").get_data(as_text=True)
    assert "Soll-Stand" in page
