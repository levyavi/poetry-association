import pytest

from poem_assoc.app import create_app
from poem_assoc.config import Config
from poem_assoc.db import get_connection, init_db
from poem_assoc.embedding import EmbeddingService
from poem_assoc.lexical import LexicalTextProcessor


@pytest.fixture(scope="session")
def embedding_service():
    """Return a real EmbeddingService shared across all tests (model loaded once)."""
    return EmbeddingService("all-MiniLM-L6-v2")


@pytest.fixture()
def temp_db_path(tmp_path):
    """Return a path to a temporary SQLite database file (does not pre-create it)."""
    return str(tmp_path / "test_poem_assoc.db")


@pytest.fixture()
def db_conn(temp_db_path):
    """Return a connection to a fresh, schema-initialized temp database."""
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    yield conn
    conn.close()


@pytest.fixture()
def lexical_processor():
    """Return a validated lexical processor backed by bundled offline resources."""
    cfg = Config(
        db_path="./unused.db",
        secret_key="test-secret",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
    )
    processor = LexicalTextProcessor(cfg.nltk_data_path)
    processor.validate_resources()
    return processor


@pytest.fixture()
def app(temp_db_path, embedding_service):
    """Return a Flask app bound to a temporary database."""
    cfg = Config(
        db_path=temp_db_path,
        secret_key="test-secret",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
    )
    flask_app = create_app(config_override=cfg, embedding_service=embedding_service)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    """Return a Flask test client."""
    return app.test_client()
