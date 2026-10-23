import os

import click
from dotenv import load_dotenv
from flask import Flask
from werkzeug.security import generate_password_hash

from app.config import Config
from app.extensions import db

load_dotenv()


def create_app(config_object=Config):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_object)

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
    app.context_processor(lambda: {"current_user": current_user()})

    with app.app_context():
        db.create_all()
        _bootstrap_admin(app)

    @app.cli.command("create-admin")
    @click.argument("username")
    @click.option("--name", default=None, help="Anzeigename (Standard: Benutzername)")
    @click.password_option(help="Passwort (mind. 8 Zeichen)")
    def create_admin(username, name, password):
        """Legt einen Admin an oder setzt bei einem bestehenden Konto Passwort und Admin-Recht."""
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
        click.echo(f"Admin '{username}' ist eingerichtet.")

    return app


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
    db.session.commit()
    app.logger.warning(
        "Erst-Admin '%s' angelegt. ADMIN_PASSWORD jetzt aus der Umgebung entfernen.", username
    )
