import os
import sqlite3
import time

import pytest

from poem_assoc.app import create_app
from poem_assoc.config import Config
from poem_assoc.db import get_connection, init_db


def test_config_reads_defaults(monkeypatch):
    monkeypatch.delenv("POEM_DB_PATH", raising=False)
    monkeypatch.delenv("POEM_SECRET_KEY", raising=False)
    monkeypatch.delenv("POEM_ADMIN_PASSWORD", raising=False)
    cfg = Config.from_environment()
    assert cfg.db_path == "./poem_assoc.db"
    assert cfg.secret_key
    assert cfg.admin_password == ""


def test_config_reads_environment(monkeypatch, tmp_path):
    custom_path = str(tmp_path / "custom.db")
    monkeypatch.setenv("POEM_DB_PATH", custom_path)
    cfg = Config.from_environment()
    assert cfg.db_path == custom_path


def test_init_db_creates_schema(temp_db_path):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    rows = conn.execute("PRAGMA table_info(poems)").fetchall()
    conn.close()
    col_names = [row["name"] for row in rows]
    for expected in (
        "id",
        "title",
        "text",
        "cleaned_text",
        "lemmatized_search_text",
        "embedding",
        "created_at",
        "updated_at",
    ):
        assert expected in col_names, f"Missing column: {expected}"


def test_init_db_idempotent(temp_db_path):
    init_db(temp_db_path)
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    rows = conn.execute("PRAGMA table_info(poems)").fetchall()
    conn.close()
    assert len(rows) == 8


def test_create_app_returns_flask_app(app):
    from flask import Flask

    assert isinstance(app, Flask)


def test_search_page_returns_200(client):
    resp = client.get("/")
    assert resp.status_code == 200


def test_search_page_contains_form(client):
    resp = client.get("/")
    html = resp.data.decode()
    assert 'name="q"' in html
    assert "autofocus" in html
    assert 'type="submit"' in html or "<button" in html


def test_db_file_created(temp_db_path):
    cfg = Config(
        db_path=temp_db_path,
        secret_key="s",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
    )
    create_app(config_override=cfg)
    assert os.path.exists(temp_db_path)


def test_poems_table_columns(temp_db_path):
    init_db(temp_db_path)
    conn = sqlite3.connect(temp_db_path)
    cursor = conn.execute("PRAGMA table_info(poems)")
    cols = {row[1] for row in cursor.fetchall()}
    conn.close()
    assert cols == {
        "id",
        "title",
        "text",
        "cleaned_text",
        "lemmatized_search_text",
        "embedding",
        "created_at",
        "updated_at",
    }


def test_startup_under_two_seconds(tmp_path):
    db = str(tmp_path / "perf.db")
    cfg = Config(
        db_path=db,
        secret_key="s",
        admin_password="test-pass",
        model_name="all-MiniLM-L6-v2",
        model_path=None,
    )
    start = time.monotonic()
    create_app(config_override=cfg)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"create_app took {elapsed:.2f}s, expected < 2s"
