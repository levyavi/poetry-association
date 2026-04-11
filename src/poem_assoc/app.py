from __future__ import annotations

from flask import Flask

from .config import Config
from .db import init_db
from .routes.public import public_bp


def create_app(config_override: Config | None = None) -> Flask:
    """Build and return a configured Flask application instance."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    cfg = config_override if config_override is not None else Config.from_environment()

    app.config["SECRET_KEY"] = cfg.secret_key
    app.config["POEM_CONFIG"] = cfg

    init_db(cfg.db_path)

    app.register_blueprint(public_bp)

    return app
