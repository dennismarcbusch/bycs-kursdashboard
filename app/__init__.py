import os
import secrets
from datetime import timezone
from zoneinfo import ZoneInfo

import click
from dotenv import load_dotenv

# Vor dem Import von app.config laden: Config liest die Umgebung beim Import.
load_dotenv()

from flask import Flask  # noqa: E402
from sqlalchemy.exc import IntegrityError, OperationalError  # noqa: E402
from werkzeug.middleware.proxy_fix import ProxyFix  # noqa: E402
from werkzeug.security import generate_password_hash  # noqa: E402

from app.config import INSECURE_SECRET_KEYS, Config  # noqa: E402
from app.extensions import db  # noqa: E402


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)
    _ensure_secret_key(app)
    if app.config["PROXY_COUNT"] > 0:
        n = app.config["PROXY_COUNT"]
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=n, x_proto=n, x_host=n)

    os.makedirs(app.instance_path, exist_ok=True)
    app.config.setdefault(
        "SQLALCHEMY_DATABASE_URI",
        "sqlite:///" + os.path.join(app.instance_path, "app.db"),
    )
    if os.environ.get("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]

    db.init_app(app)

    from app.admin.routes import bp as admin_bp
    from app.auth.decorators import current_user
    from app.auth.routes import bp as auth_bp
    from app.dashboard.routes import bp as dashboard_bp
    from app.dashboard.topics_routes import bp as topics_bp
    from app.security import init_csrf

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(topics_bp)

    init_csrf(app)
    display_tz = ZoneInfo(app.config["DISPLAY_TIMEZONE"])

    @app.template_filter("localtime")
    def localtime(value):
        """Gespeicherten UTC-Zeitpunkt in Ortszeit umrechnen (SQLite liefert ihn ohne Zone)."""
        if value is None:
            return None
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(display_tz)

    app.context_processor(lambda: {"current_user": current_user()})

    with app.app_context():
        try:
            db.create_all()
        except OperationalError:
            # Mehrere Worker starten gleichzeitig; ein anderer hat die Tabellen schon angelegt.
            db.session.rollback()
            db.create_all()
        _bootstrap_admin(app)

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.option("--name", default=None, help="Anzeigename (Standard: Benutzername)")
    @click.password_option(help="Passwort (mind. 8 Zeichen)")
    def create_admin(username, name, password):
        """Legt einen Admin an oder setzt bei einem bestehenden Konto Passwort und Admin-Recht."""
        from app.auth import throttle
        from app.auth.routes import MIN_PASSWORD_LENGTH
        from app.models import User

        username = username.strip().lower()
        if len(password) < MIN_PASSWORD_LENGTH:
            raise click.ClickException(f"Das Passwort braucht mindestens {MIN_PASSWORD_LENGTH} Zeichen.")
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username, display_name=name or username)
            db.session.add(user)
        user.password_hash = generate_password_hash(password)
        user.is_admin = True
        user.is_active = True
        db.session.commit()
        throttle.reset(username)  # hebt eine Login-Sperre des Kontos auf
        click.echo(f"Admin '{username}' ist eingerichtet.")

    return app


def _ensure_secret_key(app):
    """Ohne echtes SECRET_KEY könnte jeder ein Sitzungscookie (z. B. als Admin) fälschen.

    Fehlt der Schlüssel oder ist es ein bekannter Platzhalter, wird ein zufälliger erzeugt.
    Sitzungen überleben dann keinen Neustart - daher die Warnung."""
    key = app.config.get("SECRET_KEY")
    if key and key not in INSECURE_SECRET_KEYS:
        return
    if app.testing:
        return
    app.config["SECRET_KEY"] = secrets.token_hex(32)
    app.logger.warning(
        "SECRET_KEY fehlt oder ist ein Platzhalter; es wird ein zufälliger Schlüssel genutzt. "
        "Für dauerhafte Sitzungen SECRET_KEY setzen (z. B. python -c "
        "\"import secrets; print(secrets.token_hex(32))\")."
    )


def _bootstrap_admin(app):
    """Legt beim allerersten Start einen Admin aus ADMIN_USERNAME/ADMIN_PASSWORD an."""
    from app.models import User

    password = app.config.get("ADMIN_PASSWORD")
    if not password or User.query.count() > 0:
        return
    username = (app.config.get("ADMIN_USERNAME") or "admin").strip().lower()
    db.session.add(
        User(
            username=username,
            display_name=username,
            password_hash=generate_password_hash(password),
            is_admin=True,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        # Ein parallel startender Worker hat den Admin bereits angelegt.
        db.session.rollback()
        return
    app.logger.warning(
        "Erst-Admin '%s' angelegt. ADMIN_PASSWORD jetzt aus der Umgebung entfernen.", username
    )
