import io
from datetime import datetime
from pathlib import Path

import pytest

from app.dashboard.stats import build_stats
from app.extensions import db
from app.importer.csv_parser import CsvParseError, import_csv
from app.models import ClassDashboard

FIXTURES = Path(__file__).parent / "fixtures"


def _make_dashboard():
    cd = ClassDashboard(owner_username="testlehrer", name="Testklasse")
    db.session.add(cd)
    db.session.commit()
    return cd


def test_import_parses_students_activities_and_records(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f, original_filename="sample_progress.csv")
    db.session.commit()

    assert {s.full_name for s in cd.students} == {"Erika Musterfrau", "Max Mustermann"}
    # "Checkliste A" kommt zweimal im Header vor -> muss disambiguiert werden.
    assert {a.name for a in cd.activities} == {"Checkliste A", "Aufgabe B", "Checkliste A (2)"}
    assert len(imp.records) == 2 * 3  # 2 Schüler:innen x 3 Aktivitäten


def test_completed_status_and_timestamp_parsed(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f)
    db.session.commit()

    erika = next(s for s in cd.students if s.full_name == "Erika Musterfrau")
    checkliste_a = next(a for a in cd.activities if a.name == "Checkliste A")

    record = next(
        r for r in imp.records if r.student_id == erika.id and r.activity_id == checkliste_a.id
    )
    assert record.completed is True
    assert record.completed_at == datetime(2025, 10, 1, 9, 0)

    max_ = next(s for s in cd.students if s.full_name == "Max Mustermann")
    record_max = next(
        r for r in imp.records if r.student_id == max_.id and r.activity_id == checkliste_a.id
    )
    assert record_max.completed is False
    assert record_max.completed_at is None


def test_repeated_import_reuses_existing_students_and_activities(app):
    cd = _make_dashboard()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        import_csv(cd, f)
    db.session.commit()

    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        import_csv(cd, f)
    db.session.commit()

    assert len(cd.students) == 2
    assert len(cd.activities) == 3
    assert len(cd.imports) == 2


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
