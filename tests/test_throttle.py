from datetime import timedelta

from app.auth import throttle
from app.extensions import db
from app.models import LoginThrottle

from conftest import login, make_user


def _fail(client, username="lehrer", times=1, ip="10.0.0.1"):
    for _ in range(times):
        resp = client.post(
            "/login",
            data={"username": username, "password": "falsch"},
            environ_base={"REMOTE_ADDR": ip},
        )
    return resp


def _login_from(client, username="lehrer", ip="10.0.0.1"):
    return client.post(
        "/login",
        data={"username": username, "password": "passwort123"},
        environ_base={"REMOTE_ADDR": ip},
    )


def test_account_is_locked_after_max_failures(app, client):
    make_user("lehrer")
    _fail(client, times=4)
    assert _login_from(client).status_code == 302  # 4 Fehlversuche: noch erlaubt

    client.post("/logout")
    resp = _fail(client, times=5)
    assert resp.status_code == 200  # der 5. Fehlversuch wird noch normal beantwortet
    resp = _login_from(client)
    assert resp.status_code == 429  # jetzt gesperrt, auch mit richtigem Passwort
    assert "Zu viele fehlgeschlagene" in resp.get_data(as_text=True)
    # Andere Adresse hilft nicht: die Sperre hängt am Benutzernamen.
    assert _login_from(client, ip="10.0.0.2").status_code == 429


def test_successful_login_resets_counter(app, client):
    make_user("lehrer")
    _fail(client, times=4)
    assert _login_from(client).status_code == 302
    client.post("/logout")
    _fail(client, times=4)
    assert _login_from(client).status_code == 302


def test_lock_expires(app, client):
    make_user("lehrer")
    _fail(client, times=5)
    assert _login_from(client).status_code == 429
    row = LoginThrottle.query.filter_by(key="user:lehrer").one()
    row.locked_until = throttle._now() - timedelta(seconds=1)
    db.session.commit()
    assert _login_from(client).status_code == 302


def test_old_failures_expire(app, client):
    make_user("lehrer")
    _fail(client, times=4)
    for row in LoginThrottle.query.all():
        row.last_failure_at = throttle._now() - timedelta(minutes=16)
    db.session.commit()
    _fail(client, times=1)
    assert _login_from(client).status_code == 302


def test_unknown_usernames_are_locked_too(app, client):
    _fail(client, username="gibtsnicht", times=5)
    resp = _fail(client, username="gibtsnicht")
    assert resp.status_code == 429


def test_ip_is_locked_after_many_usernames(app, client):
    make_user("lehrer")
    for i in range(20):
        _fail(client, username=f"name{i}")
    assert _login_from(client).status_code == 429
    assert _login_from(client, ip="10.0.0.9").status_code == 302


def test_admin_can_unlock_and_password_reset_unlocks(app, client):
    user = make_user("lehrer")
    make_user("chef", admin=True)
    _fail(client, times=5)
    assert _login_from(client).status_code == 429

    admin = app.test_client()
    login(admin, "chef")
    assert "Login gesperrt bis" in admin.get(f"/admin/users/{user.id}").get_data(as_text=True)
    admin.post(f"/admin/users/{user.id}/unlock")
    assert _login_from(client).status_code == 302

    client.post("/logout")
    _fail(client, times=5)
    admin.post(
        f"/admin/users/{user.id}",
        data={"display_name": "Lehrer", "password": "ganz-neues-pw", "is_active": "1"},
    )
    resp = client.post(
        "/login", data={"username": "lehrer", "password": "ganz-neues-pw"},
        environ_base={"REMOTE_ADDR": "10.0.0.1"},
    )
    assert resp.status_code == 302


def test_unlock_requires_admin(app, client):
    user = make_user("lehrer")
    login(client, "lehrer")
    assert client.post(f"/admin/users/{user.id}/unlock").status_code == 403


def test_minutes_until_rounds_up():
    now = throttle._now()
    assert throttle.minutes_until(now + timedelta(minutes=14, seconds=1)) == 15
    assert throttle.minutes_until(now - timedelta(minutes=1)) == 1
