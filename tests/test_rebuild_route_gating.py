"""Tests for rebuild route and lock gating on search/admin mutation routes."""

import numpy as np

from poem_assoc.db import get_connection, init_db
from poem_assoc.startup_upgrade import UpgradeStatus
from poem_assoc.text_cleaning import clean_poem_text, compute_dedup_key


def _login(client, password="test-pass"):
    client.post("/admin/login", data={"password": password})


def _get_csrf_token(client):
    client.get("/admin/")
    with client.session_transaction() as sess:
        return sess["csrf_token"]


def _seed_poem(app, embedding_service, title="Test Poem", text="Some poem text"):
    cfg = app.config["POEM_CONFIG"]
    conn = get_connection(cfg.db_path)
    try:
        cleaned = clean_poem_text(text)
        dedup = compute_dedup_key(cleaned)
        vector = embedding_service.encode(title, cleaned)
        blob = embedding_service.to_bytes(vector)
        with conn:
            cur = conn.execute(
                "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')",
                (title, text, dedup, blob),
            )
        return cur.lastrowid
    finally:
        conn.close()


class TestSearchReturns503DuringRebuild:
    def test_search_503_when_lock_held(self, app, client):
        lock = app.extensions["rebuild_lock"]
        lock.acquire()
        try:
            resp = client.post("/search", data={"q": "test"})
            assert resp.status_code == 503
            assert b"temporarily disabled" in resp.data
        finally:
            lock.release()

    def test_search_works_when_lock_not_held(self, app, client, embedding_service):
        _seed_poem(app, embedding_service)
        resp = client.post("/search", data={"q": "poem"})
        assert resp.status_code == 200


class TestAdminMutationsBlockedDuringRebuild:
    def test_add_blocked(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                "/admin/poems",
                data={"title": "X", "text": "Y", "csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_edit_blocked(self, app, client, embedding_service):
        poem_id = _seed_poem(app, embedding_service)
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                f"/admin/poems/{poem_id}/edit",
                data={"title": "X", "text": "Y", "csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_delete_blocked(self, app, client, embedding_service):
        poem_id = _seed_poem(app, embedding_service)
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                f"/admin/poems/{poem_id}/delete",
                data={"csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_import_preview_blocked(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                "/admin/import/preview",
                data={"csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_import_confirm_blocked(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                "/admin/import/confirm",
                data={"csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_import_cancel_blocked(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.post(
                "/admin/import/cancel",
                data={"csrf_token": "x"},
                follow_redirects=False,
            )
            assert resp.status_code == 302
        finally:
            lock.release()

    def test_add_blocked_when_startup_upgrade_running(self, app, client, monkeypatch):
        coordinator = app.extensions["startup_upgrade"]
        monkeypatch.setattr(coordinator, "status", lambda: UpgradeStatus.running())
        _login(client)

        resp = client.post(
            "/admin/poems",
            data={"title": "X", "text": "Y", "csrf_token": "x"},
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"Search data is still being upgraded" in resp.data

    def test_import_preview_blocked_when_startup_upgrade_failed(self, app, client):
        app.extensions["startup_upgrade"].mark_failed("automatic upgrade failed")
        _login(client)

        resp = client.post(
            "/admin/import/preview",
            data={"csrf_token": "x"},
            follow_redirects=True,
        )

        assert resp.status_code == 200
        assert b"retry the rebuild before changing poems" in resp.data


class TestRebuildRoute:
    def test_rebuild_requires_auth(self, client):
        resp = client.post("/admin/rebuild", data={"csrf_token": "x"})
        # Should redirect to login
        assert resp.status_code == 302
        assert "/login" in resp.headers.get("Location", "")

    def test_rebuild_requires_csrf(self, app, client):
        _login(client)
        resp = client.post("/admin/rebuild", data={})
        assert resp.status_code == 400

    def test_rebuild_success(self, app, client, embedding_service):
        _seed_poem(app, embedding_service, "Rose", "A rose is a rose")
        _seed_poem(app, embedding_service, "Sky", "The sky is blue today")
        _login(client)
        token = _get_csrf_token(client)

        resp = client.post("/admin/rebuild", data={"csrf_token": token})
        assert resp.status_code == 200
        assert b"Rebuild complete" in resp.data
        assert b"2" in resp.data  # 2 poems rebuilt

    def test_second_rebuild_rejected_while_first_held(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        token = _get_csrf_token(client)
        lock.acquire()
        try:
            resp = client.post(
                "/admin/rebuild",
                data={"csrf_token": token},
                follow_redirects=True,
            )
            assert b"already in progress" in resp.data
        finally:
            lock.release()

    def test_lock_released_after_rebuild_failure(self, app, client, embedding_service):
        _seed_poem(app, embedding_service, "Poem", "Some text here")
        _login(client)
        token = _get_csrf_token(client)

        # Monkey-patch embedding service to fail
        original_encode = embedding_service.encode

        def failing_encode(title, text):
            raise RuntimeError("model exploded")

        embedding_service.encode = failing_encode
        try:
            resp = client.post("/admin/rebuild", data={"csrf_token": token})
            assert resp.status_code == 200
            assert b"error" in resp.data.lower() or b"model exploded" in resp.data
        finally:
            embedding_service.encode = original_encode

        lock = app.extensions["rebuild_lock"]
        assert not lock.is_rebuilding()
        assert lock.acquire() is True  # Can re-acquire
        lock.release()

    def test_manual_rebuild_retry_allowed_after_startup_upgrade_failure(
        self, app, client, embedding_service
    ):
        _seed_poem(app, embedding_service, "Legacy", "Leaves were falling")
        app.extensions["startup_upgrade"].mark_failed("automatic upgrade failed")
        _login(client)
        token = _get_csrf_token(client)

        resp = client.post("/admin/rebuild", data={"csrf_token": token})

        assert resp.status_code == 200
        assert b"Rebuild complete" in resp.data
        assert app.extensions["startup_upgrade"].status().state == "ready"


class TestDashboardRebuildButton:
    def test_dashboard_contains_rebuild_button(self, client):
        _login(client)
        resp = client.get("/admin/")
        assert resp.status_code == 200
        assert b"Rebuild all embeddings" in resp.data
        assert b"/admin/rebuild" in resp.data

    def test_admin_banner_visible_while_rebuilding(self, app, client):
        lock = app.extensions["rebuild_lock"]
        _login(client)
        lock.acquire()
        try:
            resp = client.get("/admin/")
            assert b"rebuild in progress" in resp.data.lower()
        finally:
            lock.release()

    def test_admin_banner_hidden_when_idle(self, client):
        _login(client)
        resp = client.get("/admin/")
        assert b"rebuild in progress" not in resp.data.lower()


class TestSearch503PageRendering:
    def test_503_page_renders_message(self, app, client):
        lock = app.extensions["rebuild_lock"]
        lock.acquire()
        try:
            resp = client.post("/search", data={"q": "anything"})
            assert resp.status_code == 503
            assert b"temporarily disabled" in resp.data
            assert b"being rebuilt" in resp.data
        finally:
            lock.release()


class TestRebuildPerformance:
    def test_rebuild_5_poems_under_10s(self, app, client, embedding_service):
        import time

        for i in range(5):
            _seed_poem(app, embedding_service, f"Poem {i}", f"Unique text number {i}")

        _login(client)
        token = _get_csrf_token(client)

        start = time.monotonic()
        resp = client.post("/admin/rebuild", data={"csrf_token": token})
        elapsed = time.monotonic() - start

        assert resp.status_code == 200
        assert elapsed < 10.0
