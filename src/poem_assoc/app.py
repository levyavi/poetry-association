from __future__ import annotations

import logging

from flask import Flask, render_template, request

from .config import Config
from .csrf import issue_token as csrf_issue_token
from .db import init_db
from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor
from .locks import RebuildLock
from .routes.admin import admin_bp
from .routes.public import public_bp
from .search import SearchService
from .startup_upgrade import StartupUpgradeCoordinator
from .synonyms import SynonymExpander


def _configure_search_logger(log_level: str) -> logging.Logger:
    logger = logging.getLogger("poem_assoc.search")
    level = logging.getLevelNamesMapping().get(log_level.upper(), logging.WARNING)

    if not any(
        getattr(handler, "_poem_assoc_search_handler", False)
        for handler in logger.handlers
    ):
        handler = logging.StreamHandler()
        handler._poem_assoc_search_handler = True
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)

    logger.setLevel(level)
    logger.propagate = False
    for handler in logger.handlers:
        handler.setLevel(level)
    return logger


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

    search_logger = _configure_search_logger(cfg.log_level)
    app.extensions["search_logger"] = search_logger

    lexical_processor = LexicalTextProcessor(cfg.nltk_data_path)
    lexical_processor.validate_resources()
    app.extensions["lexical"] = lexical_processor
    synonym_expander = SynonymExpander(lexical_processor)
    app.extensions["synonyms"] = synonym_expander

    init_db(cfg.db_path)

    # Load embedding model once at startup (or reuse an injected instance).
    if embedding_service is None:
        model_ref = cfg.model_path if cfg.model_path else cfg.model_name
        embedding_service = EmbeddingService(model_ref)
        print(f"embedding model ready ({cfg.model_name})", flush=True)

    app.extensions["embedding"] = embedding_service

    search_service = SearchService(
        cfg.db_path,
        embedding_service,
        lexical_processor,
        synonym_expander=synonym_expander,
        enable_synonym_expansion=cfg.enable_synonym_expansion,
        logger=search_logger,
    )
    app.extensions["search"] = search_service

    rebuild_lock = RebuildLock()
    app.extensions["rebuild_lock"] = rebuild_lock

    startup_upgrade = StartupUpgradeCoordinator(
        cfg.db_path,
        embedding_service,
        lexical_processor,
        search_service,
        rebuild_lock,
    )
    app.extensions["startup_upgrade"] = startup_upgrade

    app.jinja_env.globals["csrf_token"] = csrf_issue_token

    @app.context_processor
    def _inject_rebuild_state():
        startup_status = startup_upgrade.status()
        rebuild_in_progress = rebuild_lock.is_rebuilding()
        return {
            "rebuild_in_progress": rebuild_in_progress,
            "search_available": (
                startup_status.is_search_available() and not rebuild_in_progress
            ),
            "admin_write_available": (
                startup_status.is_write_available() and not rebuild_in_progress
            ),
            "startup_upgrade_status": startup_status,
        }

    @app.before_request
    def _block_search_during_startup_upgrade():
        if request.endpoint != "public.search":
            return None

        startup_status = startup_upgrade.status()
        if startup_status.is_search_available():
            return None

        display_q = request.form.get("q", "").strip()
        return render_template("search.html", q=display_q, results=None), 503

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    startup_upgrade.begin_if_needed()

    return app
