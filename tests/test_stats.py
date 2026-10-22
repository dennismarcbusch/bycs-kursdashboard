from app.dashboard.stats import build_stats, build_student_detail
from app.extensions import db
from app.importer.csv_parser import import_csv
from app.models import ClassDashboard

import io

HEADER = ",E-Mail-Adresse,Institution,A,,B,,C,,D,\n"


def _csv(rows):
    # rows: (name, [bool, ...]) -> Moodle-Format ohne Datumsspalten
    lines = [",E-Mail-Adresse,Institution,A,B,C,D"]
    for name, flags in rows:
        cells = ["Abgeschlossen" if f else "Nicht abgeschlossen" for f in flags]
        lines.append(",".join([name, "x", "1"] + cells))
    return io.StringIO("\n".join(lines) + "\n")


def _make_class(rows):
    cd = ClassDashboard(owner_username="t", name="Testklasse")
    db.session.add(cd)
    import_csv(cd, _csv(rows))
    db.session.commit()
    return cd


ROWS = [
    ("Anna", [True, True, True, True]),    # 100
    ("Ben", [True, True, True, False]),    # 75
    ("Cora", [True, True, False, False]),  # 50
    ("Dan", [True, False, False, False]),  # 25
    ("Eva", [False, False, False, False]), # 0
]


def test_groups_median_and_ranking(app):
    cd = _make_class(ROWS)
    stats = build_stats(cd, cd.imports[0])

    assert stats["median"] == 50.0
    assert [s["name"] for s in stats["ranking"]] == ["Anna", "Ben", "Cora", "Dan", "Eva"]
    groups = {s["name"]: s["group"] for s in stats["ranking"]}
    assert groups == {
        "Anna": "vorn",
        "Ben": "vorn",
        "Cora": "feld",
        "Dan": "hinterher",
        "Eva": "hinterher",
    }
    assert stats["group_counts"] == {"vorn": 2, "feld": 1, "hinterher": 2}
    assert [r["student_name"] for r in stats["heatmap"]["rows"]][0] == "Anna"


def test_small_class_is_not_classified(app):
    cd = _make_class(ROWS[:3])
    stats = build_stats(cd, cd.imports[0])
    assert {s["group"] for s in stats["ranking"]} == {"feld"}


def test_open_activities_sorted_by_open_count(app):
    cd = _make_class(ROWS)
    stats = build_stats(cd, cd.imports[0])
    open_activities = stats["open_activities"]
    assert [a["name"] for a in open_activities] == ["D", "C", "B", "A"]
    assert [a["open_count"] for a in open_activities] == [4, 3, 2, 1]
    assert [s["name"] for s in open_activities[-1]["students"]] == ["Eva"]


def test_student_detail_marks_gaps_and_class_context(app):
    cd = _make_class([("Anna", [True, False, True, False])] + ROWS[1:])
    student = next(s for s in cd.latest_import.students if s.full_name == "Anna")
    detail = build_student_detail(cd, cd.imports[0], student)

    assert detail["open"] == 2
    # B ist offen, obwohl C danach erledigt ist -> Lücke; D ist nur offen.
    assert [(a["name"], a["gap"]) for a in detail["open_list"]] == [("B", True), ("D", False)]
    assert detail["gap_count"] == 1
    assert detail["class"]["student_count"] == 5
    assert [s["name"] for s in detail["students"]] == ["Anna", "Ben", "Cora", "Dan", "Eva"]


def test_delta_since_previous_import(app):
    cd = _make_class(ROWS)
    import_csv(
        cd,
        _csv([("Anna", [True, True, True, True]), ("Eva", [True, True, False, False])]),
    )
    db.session.commit()
    latest = cd.imports[0]
    stats = build_stats(cd, latest)
    by_name = {s["name"]: s for s in stats["ranking"]}
    assert by_name["Eva"]["delta"] == 2
    assert by_name["Anna"]["delta"] == 0


def test_delta_ignores_added_and_removed_activities(app):
    cd = _make_class([("Anna", [True, False, False, False])])
    # B entfällt, E kommt neu hinzu (für Anna erledigt): beides darf kein Delta erzeugen.
    text = ",E-Mail-Adresse,Institution,A,C,D,E\nAnna,x,1,Abgeschlossen,Abgeschlossen,Nicht abgeschlossen,Abgeschlossen\n"
    import_csv(cd, io.StringIO(text))
    db.session.commit()
    stats = build_stats(cd, cd.latest_import)
    assert stats["ranking"][0]["delta"] == 1  # nur C ist gegenüber A, C, D neu
