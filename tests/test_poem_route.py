import pytest

from poem_assoc import repository
from poem_assoc.db import get_connection


def test_poem_route_returns_json(client, app):
    """Test that GET /poems/<id> returns JSON with the expected structure."""
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem_id = repository.create_poem(
            conn,
            "Test Poem",
            "Line 1\nLine 2\nLine 3",
            app.extensions["embedding"],
            app.extensions["lexical"],
        )
    finally:
        conn.close()

    response = client.get(f"/poems/{poem_id}")
    assert response.status_code == 200
    assert response.content_type == "application/json"

    data = response.get_json()
    assert data["id"] == poem_id
    assert data["title"] == "Test Poem"
    assert data["text"] == "Line 1\nLine 2\nLine 3"


def test_poem_route_404_for_missing(client):
    """Test that GET /poems/<id> returns 404 for non-existent poems."""
    response = client.get("/poems/9999")
    assert response.status_code == 404


def test_poem_route_title_only_poem(client, app):
    """Test that poems with empty body are stored and retrieved correctly."""
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem_id = repository.create_poem(
            conn,
            "Title Only",
            "",
            app.extensions["embedding"],
            app.extensions["lexical"],
        )
    finally:
        conn.close()

    response = client.get(f"/poems/{poem_id}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["title"] == "Title Only"
    assert data["text"] == ""


def test_poem_route_preserves_line_breaks(client, app):
    """Test that line breaks are preserved in the JSON response."""
    poem_text = "First line\nSecond line\nThird line with\nmultiple breaks"
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        poem_id = repository.create_poem(
            conn,
            "Multiline Poem",
            poem_text,
            app.extensions["embedding"],
            app.extensions["lexical"],
        )
    finally:
        conn.close()

    response = client.get(f"/poems/{poem_id}")
    assert response.status_code == 200

    data = response.get_json()
    assert data["text"] == poem_text
    assert "\n" in data["text"]
