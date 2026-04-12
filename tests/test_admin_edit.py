"""Tests for admin edit poem functionality."""

import time

from poem_assoc.db import get_connection
from poem_assoc.repository import create_poem, get_poem


def _login(client, password="test-pass"):
    client.post("/admin/login", data={"password": password})


def _get_csrf_token(client):
    client.get("/admin/poems/new")
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def _seed_poem(
    app,
    embedding_service,
    lexical_processor,
    title="Original",
    text="Original poem text body",
):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    poem_id = create_poem(conn, title, text, embedding_service, lexical_processor)
    conn.close()
    return poem_id


class TestAdminEdit:
    def test_edit_form_prefilled(self, app, client, embedding_service, lexical_processor):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        resp = client.get(f"/admin/poems/{poem_id}/edit")
        assert resp.status_code == 200
        assert b"Original" in resp.data
        assert b"Original poem text body" in resp.data

    def test_edit_success(self, app, client, embedding_service, lexical_processor):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        token = _get_csrf_token(client)

        resp = client.post(
            f"/admin/poems/{poem_id}/edit",
            data={
                "csrf_token": token,
                "title": "Updated Title",
                "text": "Updated poem text body",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Saved" in resp.data
        assert b"Updated Title" in resp.data

    def test_edit_bumps_updated_at(self, app, client, embedding_service, lexical_processor):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        before = get_poem(conn, poem_id)
        conn.close()

        time.sleep(1.1)
        _login(client)
        token = _get_csrf_token(client)
        client.post(
            f"/admin/poems/{poem_id}/edit",
            data={
                "csrf_token": token,
                "title": "Changed",
                "text": "Changed poem text body",
            },
            follow_redirects=True,
        )

        conn = get_connection(cfg.db_path)
        after = get_poem(conn, poem_id)
        conn.close()
        assert after["updated_at"] > before["updated_at"]
        assert after["created_at"] == before["created_at"]

    def test_edit_unchanged_preserves_updated_at(
        self, app, client, embedding_service, lexical_processor
    ):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        before = get_poem(conn, poem_id)
        conn.close()

        _login(client)
        token = _get_csrf_token(client)
        client.post(
            f"/admin/poems/{poem_id}/edit",
            data={
                "csrf_token": token,
                "title": "Original",
                "text": "Original poem text body",
            },
            follow_redirects=True,
        )

        conn = get_connection(cfg.db_path)
        after = get_poem(conn, poem_id)
        conn.close()
        assert after["updated_at"] == before["updated_at"]

    def test_edit_duplicate_blocked(self, app, client, embedding_service, lexical_processor):
        _seed_poem(app, embedding_service, lexical_processor, title="A", text="Text alpha")
        poem_id_b = _seed_poem(
            app, embedding_service, lexical_processor, title="B", text="Text beta"
        )

        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            f"/admin/poems/{poem_id_b}/edit",
            data={
                "csrf_token": token,
                "title": "B",
                "text": "Text alpha",
            },
        )
        assert resp.status_code == 422
        assert b"already exists" in resp.data

    def test_edit_same_text_own_row_allowed(
        self, app, client, embedding_service, lexical_processor
    ):
        poem_id = _seed_poem(
            app, embedding_service, lexical_processor, title="Mine", text="My own text"
        )
        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            f"/admin/poems/{poem_id}/edit",
            data={
                "csrf_token": token,
                "title": "Mine",
                "text": "My own text",
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Saved" in resp.data

    def test_edit_missing_id_404(self, client):
        _login(client)
        resp = client.get("/admin/poems/99999/edit")
        assert resp.status_code == 404

    def test_edit_requires_csrf(self, app, client, embedding_service, lexical_processor):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        _get_csrf_token(client)
        resp = client.post(
            f"/admin/poems/{poem_id}/edit",
            data={"title": "X", "text": "Y"},
        )
        assert resp.status_code == 400
