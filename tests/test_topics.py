from pathlib import Path

from app.dashboard.stats import build_stats, build_student_detail
from app.extensions import db
from app.importer.csv_parser import import_csv
from app.models import ActivityTopic, ClassDashboard, Topic

FIXTURES = Path(__file__).parent / "fixtures"


def _make_dashboard_with_import():
    cd = ClassDashboard(name="Testklasse")
    db.session.add(cd)
    db.session.commit()
    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        imp = import_csv(cd, f)
    db.session.commit()
    return cd, imp


def test_activities_default_to_sonstige(app):
    cd, imp = _make_dashboard_with_import()
    stats = build_stats(cd, imp)
    assert [t["name"] for t in stats["per_topic"]] == ["Sonstige"]


def test_assigning_topic_moves_activity_out_of_sonstige(app):
    cd, imp = _make_dashboard_with_import()

    topic = Topic(class_dashboard=cd, name="Netzwerkgrundlagen")
    db.session.add(topic)
    db.session.commit()

    db.session.add(
        ActivityTopic(class_dashboard=cd, activity_name="Checkliste A", topic_id=topic.id)
    )
    db.session.commit()

    stats = build_stats(cd, imp)
    names = {t["name"] for t in stats["per_topic"]}
    assert names == {"Netzwerkgrundlagen", "Sonstige"}

    netzwerk = next(t for t in stats["per_topic"] if t["name"] == "Netzwerkgrundlagen")
    assert netzwerk["activity_count"] == 1
    assert netzwerk["total"] == 2  # 1 Aktivität x 2 Schüler:innen

    sonstige = next(t for t in stats["per_topic"] if t["name"] == "Sonstige")
    assert sonstige["activity_count"] == 2


def test_deleting_topic_falls_back_to_sonstige(app):
    cd, imp = _make_dashboard_with_import()
    topic = Topic(class_dashboard=cd, name="Temp")
    db.session.add(topic)
    db.session.commit()

    db.session.add(
        ActivityTopic(class_dashboard=cd, activity_name="Aufgabe B", topic_id=topic.id)
    )
    db.session.commit()

    ActivityTopic.query.filter_by(topic_id=topic.id).delete()
    db.session.delete(topic)
    db.session.commit()

    stats = build_stats(cd, imp)
    assert [t["name"] for t in stats["per_topic"]] == ["Sonstige"]


def test_heatmap_matches_topic_groups_and_students(app):
    cd, imp = _make_dashboard_with_import()
    stats = build_stats(cd, imp)

    heatmap = stats["heatmap"]
    total_activities = sum(len(g["activities"]) for g in heatmap["topic_groups"])
    assert total_activities == stats["activity_count"]

    assert len(heatmap["rows"]) == stats["student_count"]
    for row in heatmap["rows"]:
        assert len(row["cells"]) == total_activities


def test_build_student_detail_groups_by_topic(app):
    cd, imp = _make_dashboard_with_import()
    topic = Topic(class_dashboard=cd, name="Netzwerkgrundlagen")
    db.session.add(topic)
    db.session.commit()

    db.session.add(
        ActivityTopic(class_dashboard=cd, activity_name="Checkliste A", topic_id=topic.id)
    )
    db.session.commit()

    erika = next(s for s in imp.students if s.full_name == "Erika Musterfrau")
    detail = build_student_detail(cd, imp, erika)

    assert detail["student_name"] == "Erika Musterfrau"
    netzwerk = next(t for t in detail["topics"] if t["name"] == "Netzwerkgrundlagen")
    assert netzwerk["total"] == 1
    assert netzwerk["activities"][0]["name"] == "Checkliste A"
    assert netzwerk["activities"][0]["completed"] is True


def test_topic_assignment_survives_reimport(app):
    cd, imp = _make_dashboard_with_import()
    topic = Topic(class_dashboard=cd, name="Netzwerkgrundlagen")
    db.session.add(topic)
    db.session.commit()
    db.session.add(
        ActivityTopic(class_dashboard=cd, activity_name="Aufgabe B", topic_id=topic.id)
    )
    db.session.commit()

    with open(FIXTURES / "sample_progress.csv", "rb") as f:
        new_imp = import_csv(cd, f)
    db.session.commit()

    stats = build_stats(cd, new_imp)
    netzwerk = next(t for t in stats["per_topic"] if t["name"] == "Netzwerkgrundlagen")
    assert netzwerk["activity_count"] == 1
