import pytest

from poem_assoc.app import create_app
from poem_assoc.config import Config


@pytest.fixture()
def temp_db_path(tmp_path):
    """Return a path to a temporary SQLite database file (does not pre-create it)."""
    return str(tmp_path / "test_poem_assoc.db")


@pytest.fixture()
def app(temp_db_path):
    """Return a Flask app bound to a temporary database."""
    cfg = Config(
        db_path=temp_db_path,
        secret_key="test-secret",
        admin_password="",
    )
    flask_app = create_app(config_override=cfg)
    flask_app.config["TESTING"] = True
    return flask_app


@pytest.fixture()
def client(app):
    """Return a Flask test client."""
    return app.test_client()
