import io

from app import create_app
from app.extensions import db
from app.importer.csv_parser import import_csv
from app.models import ClassDashboard, User

from conftest import TestConfig, login, make_user


def _group(name, with_import=True):
    cd = ClassDashboard(name=name)
    db.session.add(cd)
    db.session.commit()
    if with_import:
        import_csv(cd, io.StringIO(",E-Mail-Adresse,A\nAnna,x,Abgeschlossen\n"))
        db.session.commit()
    return cd


def test_login_logout_and_wrong_password(app, client):
    make_user("lehrer")
    assert login(client, "lehrer", "falsch").status_code == 200  # bleibt auf der Login-Seite
    assert client.get("/").status_code == 302

    resp = login(client, "Lehrer")  # Benutzername ist nicht case-sensitiv
    assert resp.status_code == 302
    assert client.get("/").status_code == 200

    client.get("/logout")
    assert client.get("/").status_code == 302


def test_login_redirect_only_internal(app, client):
    make_user("lehrer")
    resp = client.post(
        "/login?next=//evil.example", data={"username": "lehrer", "password": "passwort123"}
    )
    assert resp.headers["Location"] == "/"


def test_inactive_user_cannot_login_and_is_logged_out_immediately(app, client):
    user = make_user("lehrer")
    login(client, "lehrer")
    assert client.get("/").status_code == 200

    user.is_active = False
    db.session.commit()
    assert client.get("/").status_code == 302  # Sitzung gilt sofort als ungültig
    assert login(client, "lehrer").status_code == 200


def test_teacher_sees_only_assigned_groups(app, client):
    mine, other = _group("ITS10 ITG10A"), _group("ITS11 ITG11B")
    make_user("lehrer", groups=[mine])
    login(client, "lehrer")

    page = client.get("/").get_data(as_text=True)
    assert "ITS10 ITG10A" in page and "ITS11 ITG11B" not in page

    assert client.get(f"/dashboards/{mine.id}").status_code == 200
    for path in (
        f"/dashboards/{other.id}",
        f"/dashboards/{other.id}/upload",
        f"/dashboards/{other.id}/topics",
    ):
        assert client.get(path).status_code == 403, path
    assert client.post(f"/dashboards/{other.id}/target", data={"target": "A"}).status_code == 403


def test_teacher_cannot_delete_group_or_open_admin(app, client):
    group = _group("ITS10 ITG10A")
    make_user("lehrer", groups=[group])
    login(client, "lehrer")

    assert client.post(f"/dashboards/{group.id}/delete").status_code == 403
    assert client.get("/admin/users").status_code == 403
    assert db.session.get(ClassDashboard, group.id) is not None


def test_admin_sees_all_groups(app, client):
    _group("ITS10 ITG10A")
    _group("ITS11 ITG11B")
    make_user("chef", admin=True)
    login(client, "chef")
    page = client.get("/").get_data(as_text=True)
    assert "ITS10 ITG10A" in page and "ITS11 ITG11B" in page


def test_admin_creates_user_and_assigns_groups(app, client):
    group = _group("ITS10 ITG10A", with_import=False)
    make_user("chef", admin=True)
    login(client, "chef")

    resp = client.post(
        "/admin/users",
        data={
            "username": "mmustermann",
            "display_name": "Max Mustermann",
            "password": "start-pw-123",
            "groups": [str(group.id)],
        },
    )
    assert resp.status_code == 302
    user = User.query.filter_by(username="mmustermann").one()
    assert user.classes == [group] and not user.is_admin

    # Neues Konto kann sich anmelden und sieht die Gruppe.
    other = app.test_client()
    assert login(other, "mmustermann", "start-pw-123").status_code == 302
    assert "ITS10 ITG10A" in other.get("/").get_data(as_text=True)


def test_admin_user_validation(app, client):
    make_user("chef", admin=True)
    login(client, "chef")
    base = {"username": "neu", "display_name": "Neu", "password": "langgenug1"}

    for bad in (
        {**base, "password": "kurz"},
        {**base, "username": "Ungültig Name"},
        {**base, "display_name": ""},
        {**base, "username": "chef"},  # existiert schon
    ):
        client.post("/admin/users", data=bad)
    assert User.query.count() == 1

    client.post("/admin/users", data=base)
    assert User.query.count() == 2


def test_admin_cannot_lock_self_out(app, client):
    chef = make_user("chef", admin=True)
    login(client, "chef")
    client.post(f"/admin/users/{chef.id}", data={"display_name": "Chef"})  # weder admin noch aktiv
    db.session.refresh(chef)
    assert chef.is_admin and chef.is_active
    client.post(f"/admin/users/{chef.id}/delete")
    assert db.session.get(User, chef.id) is not None


def test_admin_group_management(app, client):
    lehrer = make_user("lehrer")
    make_user("chef", admin=True)
    login(client, "chef")

    client.post("/admin/groups", data={"name": "ITS10 ITG10A"})
    group = ClassDashboard.query.filter_by(name="ITS10 ITG10A").one()
    client.post("/admin/groups", data={"name": "ITS10 ITG10A"})  # Duplikat
    assert ClassDashboard.query.count() == 1

    client.post(
        f"/admin/groups/{group.id}", data={"name": "ITS10 ITG10B", "members": [str(lehrer.id)]}
    )
    db.session.refresh(group)
    assert group.name == "ITS10 ITG10B" and group.members == [lehrer]

    client.post(f"/admin/groups/{group.id}/delete")
    assert ClassDashboard.query.count() == 0
    db.session.refresh(lehrer)
    assert lehrer.classes == []


def test_change_password(app, client):
    make_user("lehrer")
    login(client, "lehrer")

    client.post(
        "/account/password",
        data={"old_password": "falsch", "new_password": "neues-pw-123", "repeat_password": "neues-pw-123"},
    )
    assert login(app.test_client(), "lehrer", "neues-pw-123").status_code == 200  # noch nicht geändert

    client.post(
        "/account/password",
        data={"old_password": "passwort123", "new_password": "neues-pw-123", "repeat_password": "neues-pw-123"},
    )
    assert login(app.test_client(), "lehrer", "neues-pw-123").status_code == 302


def test_csrf_blocks_post_without_token(app):
    app.config["CSRF_ENABLED"] = True
    client = app.test_client()
    make_user("chef", admin=True)

    assert client.post("/login", data={"username": "chef", "password": "passwort123"}).status_code == 400

    page = client.get("/login").get_data(as_text=True)
    token = page.split('name="csrf_token" value="')[1].split('"')[0]
    resp = client.post(
        "/login", data={"username": "chef", "password": "passwort123", "csrf_token": token}
    )
    assert resp.status_code == 302


def test_bootstrap_admin_from_config(monkeypatch, tmp_path):
    class Cfg(TestConfig):
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'boot.db'}"
        ADMIN_USERNAME = "Erst-Admin"
        ADMIN_PASSWORD = "erstes-passwort"

    application = create_app(config_object=Cfg)
    with application.app_context():
        admin = User.query.one()
        assert admin.username == "erst-admin" and admin.is_admin
        db.session.remove()
        db.drop_all()


def test_create_admin_cli(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "Boss", "--name", "Der Boss", "--password", "langes-passwort"])
    assert result.exit_code == 0, result.output
    user = User.query.filter_by(username="boss").one()
    assert user.is_admin and user.display_name == "Der Boss"

    short = runner.invoke(args=["create-admin", "boss2", "--password", "kurz"])
    assert short.exit_code != 0
