import pytest
from werkzeug.security import generate_password_hash

from app import create_app
from app.config import Config
from app.extensions import db
from app.models import User


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SECRET_KEY = "test"
    CSRF_ENABLED = False  # gezielt in tests/test_auth.py eingeschaltet
    ADMIN_PASSWORD = ""


@pytest.fixture
def app():
    application = create_app(config_object=TestConfig)
    with application.app_context():
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def make_user(username, password="passwort123", *, admin=False, active=True, groups=()):
    user = User(
        username=username,
        display_name=username.capitalize(),
        password_hash=generate_password_hash(password),
        is_admin=admin,
        is_active=active,
    )
    user.classes = list(groups)
    db.session.add(user)
    db.session.commit()
    return user


def login(client, username, password="passwort123"):
    return client.post("/login", data={"username": username, "password": password})
