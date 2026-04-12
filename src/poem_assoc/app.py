from __future__ import annotations

from flask import Flask

from .config import Config
from .db import init_db
from .embedding import EmbeddingService
from .routes.admin import admin_bp
from .routes.public import public_bp
from .search import SearchService


def create_app(
    config_override: Config | None = None,
    embedding_service: EmbeddingService | None = None,
) -> Flask:
    """Build and return a configured Flask application instance."""
    app = Flask(__name__, template_folder="templates", static_folder="static")

    cfg = config_override if config_override is not None else Config.from_environment()

    if not cfg.admin_password:
        raise RuntimeError("POEM_ADMIN_PASSWORD must be set")

    app.config["SECRET_KEY"] = cfg.secret_key
    app.config["POEM_CONFIG"] = cfg

    init_db(cfg.db_path)

    # Load embedding model once at startup (or reuse an injected instance).
    if embedding_service is None:
        model_ref = cfg.model_path if cfg.model_path else cfg.model_name
        embedding_service = EmbeddingService(model_ref)
        print(f"embedding model ready ({cfg.model_name})", flush=True)

    app.extensions["embedding"] = embedding_service

    search_service = SearchService(cfg.db_path, embedding_service)
    app.extensions["search"] = search_service

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)

    return app
