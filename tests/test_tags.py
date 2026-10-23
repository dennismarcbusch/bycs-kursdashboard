import io

from app.dashboard.stats import build_stats
from app.extensions import db
from app.importer.csv_parser import import_csv
from app.models import ActivityTopic, ClassDashboard, Topic
from app.tags import normalize_tag, split_tag


def test_split_tag():
    assert split_tag("Checkliste ARP #ipv4") == ("Checkliste ARP", "ipv4")
    assert split_tag("Übung Größe #netz-2") == ("Übung Größe", "netz-2")
    assert split_tag("Checkliste ARP #ipv4 (2)") == ("Checkliste ARP (2)", "ipv4")
    assert split_tag("Kein Tag") == ("Kein Tag", None)
    # Ein Hashtag mitten im Namen zählt nicht.
    assert split_tag("A #x B") == ("A #x B", None)


def test_normalize_tag():
    assert normalize_tag(" #IPv4 ") == "IPv4"
    assert normalize_tag("a b") is None
    assert normalize_tag("") is None


def _class_with(header_activities):
    cd = ClassDashboard(owner_username="t", name="K")
    db.session.add(cd)
    cols = ",".join(header_activities)
    text = f",E-Mail-Adresse,{cols}\nAnna,x," + ",".join(
        ["Abgeschlossen"] + ["Nicht abgeschlossen"] * (len(header_activities) - 1)
    ) + "\nBen,x," + ",".join(["Nicht abgeschlossen"] * len(header_activities)) + "\n"
    import_csv(cd, io.StringIO(text))
    db.session.commit()
    return cd


def test_hashtag_groups_in_course_order_without_topics(app):
    cd = _class_with(["A1 #netz", "B1 #ip", "A2 #NETZ", "Ohne"])
    stats = build_stats(cd, cd.latest_import)
    names = [g["name"] for g in stats["heatmap"]["topic_groups"]]
    # Kürzel statt Name, Reihenfolge des ersten Vorkommens, Groß-/Kleinschreibung egal.
    assert names == ["netz", "ip", "Sonstige"]
    netz = stats["heatmap"]["topic_groups"][0]
    assert [a["name"] for a in netz["activities"]] == ["A1", "A2"]


def test_topic_with_tag_collects_tagged_activities(app):
    cd = _class_with(["A1 #netz", "B1 #ip", "A2 #netz"])
    db.session.add(Topic(class_dashboard=cd, name="Netzwerkgrundlagen", tag="NETZ"))
    db.session.commit()
    stats = build_stats(cd, cd.latest_import)
    by_name = {t["name"]: t for t in stats["per_topic"]}
    assert set(by_name) == {"Netzwerkgrundlagen", "ip"}
    assert by_name["Netzwerkgrundlagen"]["activity_count"] == 2


def test_manual_assignment_beats_hashtag(app):
    cd = _class_with(["A1 #netz", "B1 #ip"])
    other = Topic(class_dashboard=cd, name="Sonderthema")
    db.session.add(other)
    db.session.commit()
    db.session.add(
        ActivityTopic(class_dashboard=cd, activity_name="A1 #netz", topic_id=other.id)
    )
    db.session.commit()
    stats = build_stats(cd, cd.latest_import)
    assert {t["name"] for t in stats["per_topic"]} == {"Sonderthema", "ip"}


def test_reordering_and_removing_activities_keeps_grouping(app):
    cd = _class_with(["A1 #netz", "B1 #ip", "A2 #netz"])
    db.session.add(Topic(class_dashboard=cd, name="Netzwerk", tag="netz"))
    db.session.commit()
    # Neuer Import: umsortiert, A2 entfällt, C1 kommt hinzu.
    text = ",E-Mail-Adresse,B1 #ip,C1 #netz,A1 #netz\nAnna,x,Abgeschlossen,Abgeschlossen,Nicht abgeschlossen\nBen,x,Nicht abgeschlossen,Nicht abgeschlossen,Nicht abgeschlossen\n"
    import_csv(cd, io.StringIO(text))
    db.session.commit()
    stats = build_stats(cd, cd.latest_import)
    groups = {g["name"]: [a["name"] for a in g["activities"]] for g in stats["heatmap"]["topic_groups"]}
    assert groups == {"ip": ["B1"], "Netzwerk": ["C1", "A1"]}


def test_student_detail_uses_display_names(app):
    from app.dashboard.stats import build_student_detail

    cd = _class_with(["A1 #netz", "B1 #ip"])
    student = next(s for s in cd.latest_import.students if s.full_name == "Ben")
    detail = build_student_detail(cd, cd.latest_import, student)
    assert [a["name"] for a in detail["open_list"]] == ["A1", "B1"]
