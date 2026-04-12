"""Tests for admin delete poem functionality."""

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
    title="Deletable",
    text="This poem will be deleted",
):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    poem_id = create_poem(conn, title, text, embedding_service, lexical_processor)
    conn.close()
    return poem_id


class TestAdminDelete:
    def test_delete_confirm_renders_preview(
        self, app, client, embedding_service, lexical_processor
    ):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        resp = client.get(f"/admin/poems/{poem_id}/delete")
        assert resp.status_code == 200
        assert b"Confirm Deletion" in resp.data
        assert b"Deletable" in resp.data
        assert b"This poem will be deleted" in resp.data

    def test_delete_confirm_then_delete(
        self, app, client, embedding_service, lexical_processor
    ):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        token = _get_csrf_token(client)

        resp = client.get(f"/admin/poems/{poem_id}/delete")
        assert resp.status_code == 200

        resp = client.post(
            f"/admin/poems/{poem_id}/delete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Deleted" in resp.data

        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        assert get_poem(conn, poem_id) is None
        conn.close()

    def test_delete_removes_from_search(
        self, app, client, embedding_service, lexical_processor
    ):
        poem_id = _seed_poem(
            app,
            embedding_service,
            lexical_processor,
            title="Vanishing",
            text="The ephemeral nature of existence fades into nothing",
        )
        _login(client)
        token = _get_csrf_token(client)

        resp = client.post("/search", data={"q": "ephemeral existence fading"})
        assert b"Vanishing" in resp.data

        client.post(
            f"/admin/poems/{poem_id}/delete",
            data={"csrf_token": token},
            follow_redirects=True,
        )

        resp = client.post("/search", data={"q": "ephemeral existence fading"})
        assert b"Vanishing" not in resp.data

    def test_delete_nonexistent_poem(self, client):
        _login(client)
        token = _get_csrf_token(client)
        resp = client.post(
            "/admin/poems/99999/delete",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Poem not found" in resp.data

    def test_delete_requires_authentication(self, client):
        resp = client.post(
            "/admin/poems/1/delete",
            data={"csrf_token": "x"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_delete_requires_csrf(self, app, client, embedding_service, lexical_processor):
        poem_id = _seed_poem(app, embedding_service, lexical_processor)
        _login(client)
        _get_csrf_token(client)
        resp = client.post(
            f"/admin/poems/{poem_id}/delete",
            data={},
        )
        assert resp.status_code == 400

    def test_delete_confirm_missing_id_404(self, client):
        _login(client)
        resp = client.get("/admin/poems/99999/delete")
        assert resp.status_code == 404
