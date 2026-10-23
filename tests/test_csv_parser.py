import io
from datetime import datetime
from pathlib import Path

import pytest

from app.dashboard.stats import build_stats
from app.extensions import db
from app.importer.csv_parser import CsvParseError, import_csv
from app.models import Activity, ClassDashboard, CompletionRecord, Student

FIXTURES = Path(__file__).parent / "fixtures"


def _make_dashboard():
    cd = ClassDashboard(name="Testklasse")
    db.session.add(cd)
    db.session.commit()
    return cd


def test_import_parses_students_activities_and_records(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f, original_filename="sample_progress.csv")
    db.session.commit()

    assert {s.full_name for s in imp.students} == {"Erika Musterfrau", "Max Mustermann"}
    # "Checkliste A" kommt zweimal im Header vor -> muss disambiguiert werden; die
    # Reihenfolge entspricht den CSV-Spalten.
    assert [a.name for a in imp.activities] == ["Checkliste A", "Aufgabe B", "Checkliste A (2)"]
    assert len(imp.records) == 2 * 3  # 2 Schüler:innen x 3 Aktivitäten


def test_completed_status_and_timestamp_parsed(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f)
    db.session.commit()

    erika = next(s for s in imp.students if s.full_name == "Erika Musterfrau")
    checkliste_a = next(a for a in imp.activities if a.name == "Checkliste A")

    record = next(
        r for r in imp.records if r.student_id == erika.id and r.activity_id == checkliste_a.id
    )
    assert record.completed is True
    assert record.completed_at == datetime(2025, 10, 1, 9, 0)

    max_ = next(s for s in imp.students if s.full_name == "Max Mustermann")
    record_max = next(
        r for r in imp.records if r.student_id == max_.id and r.activity_id == checkliste_a.id
    )
    assert record_max.completed is False
    assert record_max.completed_at is None


def _import(cd, text):
    imp = import_csv(cd, io.BytesIO(text.encode("utf-8")))
    db.session.commit()
    return imp


def test_every_import_is_rebuilt_from_scratch(app):
    cd = _make_dashboard()
    _import(cd, ",E-Mail-Adresse,A,B\nAnna,x,Abgeschlossen,Nicht abgeschlossen\n")
    # B entfällt, C kommt vor A hinzu, Ben ist neu, Anna fehlt.
    imp = _import(cd, ",E-Mail-Adresse,C,A\nBen,x,Abgeschlossen,Abgeschlossen\n")

    assert [a.name for a in imp.activities] == ["C", "A"]
    assert [s.full_name for s in imp.students] == ["Ben"]
    stats = build_stats(cd, cd.latest_import)
    assert stats["activity_count"] == 2
    assert stats["overall_percent"] == 100.0
    assert len(stats["heatmap"]["rows"][0]["cells"]) == 2


def test_only_latest_two_imports_are_kept(app):
    cd = _make_dashboard()
    for n in range(4):
        _import(cd, f",E-Mail-Adresse,A\nStudent{n},x,Abgeschlossen\n")

    assert len(cd.imports) == 2
    assert [s.full_name for s in cd.imports[0].students] == ["Student3"]
    assert [s.full_name for s in cd.imports[1].students] == ["Student2"]
    # Gelöschte Importe nehmen ihre Schüler:innen, Aktivitäten und Abschlüsse mit.
    assert Student.query.count() == 2
    assert Activity.query.count() == 2
    assert CompletionRecord.query.count() == 2


def test_duplicate_student_names_are_kept_apart(app):
    cd = _make_dashboard()
    imp = _import(
        cd, ",E-Mail-Adresse,A\nAnna,x,Abgeschlossen\nAnna,y,Nicht abgeschlossen\n"
    )
    assert sorted(s.full_name for s in imp.students) == ["Anna", "Anna (2)"]
    assert len(imp.records) == 2


def test_bom_and_alternate_encoding_are_handled(app):
    cd = _make_dashboard()
    content = ",E-Mail-Adresse,Checkliste A\nMüller,xxx,Abgeschlossen\n"
    raw = content.encode("utf-8-sig")
    imp = import_csv(cd, io.BytesIO(raw))
    db.session.commit()

    assert imp.records[0].student.full_name == "Müller"


def test_empty_header_raises(app):
    cd = _make_dashboard()
    with pytest.raises(CsvParseError):
        import_csv(cd, io.BytesIO(b""))


def test_no_activity_columns_raises(app):
    cd = _make_dashboard()
    raw = ",E-Mail-Adresse,Institution\nErika,xxx,1001\n".encode("utf-8")
    with pytest.raises(CsvParseError):
        import_csv(cd, io.BytesIO(raw))


def test_build_stats(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f)
    db.session.commit()

    stats = build_stats(cd, imp)
    assert stats["student_count"] == 2
    assert stats["activity_count"] == 3
    # Erika: 2/3 abgeschlossen, Max: 1/3 abgeschlossen -> gesamt 3/6 = 50%
    assert stats["total_completed"] == 3
    assert stats["total_possible"] == 6
    assert stats["overall_percent"] == 50.0
    # Ohne Themenbereiche landet alles unter "Sonstige".
    assert len(stats["per_topic"]) == 1
    assert stats["per_topic"][0]["name"] == "Sonstige"
    assert stats["per_topic"][0]["total"] == 6
