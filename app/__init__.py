import os

from dotenv import load_dotenv
from flask import Flask

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

    from app.auth.routes import bp as auth_bp
    from app.dashboard.routes import bp as dashboard_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)

    with app.app_context():
        db.create_all()

    return app
