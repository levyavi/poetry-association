"""Tests for admin add poem functionality."""

import pytest

from poem_assoc.db import get_connection
from poem_assoc.repository import create_poem


def _login(client, password="test-pass"):
    """Authenticate the test client."""
    client.post("/admin/login", data={"password": password})


def _get_csrf_token(client):
    """Fetch the add form and extract the CSRF token from the session."""
    client.get("/admin/poems/new")
    with client.session_transaction() as sess:
        return sess["csrf_token"]


class TestAdminAdd:
    def test_add_form_renders(self, client):
        _login(client)
        resp = client.get("/admin/poems/new")
        assert resp.status_code == 200
        assert b"Add Poem" in resp.data

    def test_add_success(self, app, client, embedding_service):
        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "Test Poem",
                "text": "Roses are red\nViolets are blue",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Saved" in resp.data
        assert b"Test Poem" in resp.data

    def test_add_appears_in_search(self, app, client, embedding_service):
        _login(client)
        token = _get_csrf_token(client)
        client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "Ocean Waves",
                "text": "The ocean waves crash upon the shore with thundering might",
            },
            follow_redirects=True,
        )
        resp = client.post("/search", data={"q": "ocean waves shore"})
        assert resp.status_code == 200
        assert b"Ocean Waves" in resp.data

    def test_add_duplicate_blocked(self, app, client, embedding_service):
        _login(client)
        token = _get_csrf_token(client)
        client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "First",
                "text": "Unique poem text here",
            },
            follow_redirects=True,
        )
        resp = client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "First",
                "text": "Unique poem text here",
            },
        )
        assert resp.status_code == 422
        assert b"already exists" in resp.data

        # Only one row in DB
        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        count = conn.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
        conn.close()
        assert count == 1

    def test_add_same_body_different_title_allowed(self, app, client, embedding_service):
        _login(client)
        token = _get_csrf_token(client)
        client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "First",
                "text": "Shared body",
            },
            follow_redirects=True,
        )
        resp = client.post(
            "/admin/poems",
            data={
                "csrf_token": token,
                "title": "Second",
                "text": "Shared body",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Saved" in resp.data

    def test_add_empty_title_blocked(self, client):
        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            "/admin/poems",
            data={"csrf_token": token, "title": "   ", "text": "Body"},
        )
        assert resp.status_code == 422
        assert b"Poem title is required" in resp.data

    def test_add_empty_text_allowed(self, app, client, embedding_service):
        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            "/admin/poems",
            data={"csrf_token": token, "title": "Title Only", "text": "   "},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Saved" in resp.data
        assert b"Title Only" in resp.data

    def test_add_requires_authentication(self, client):
        resp = client.post(
            "/admin/poems",
            data={"csrf_token": "x", "title": "T", "text": "T"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_add_requires_csrf(self, client):
        _login(client)
        _get_csrf_token(client)  # ensure session has token
        resp = client.post(
            "/admin/poems",
            data={"title": "T", "text": "Some text"},
        )
        assert resp.status_code == 400
