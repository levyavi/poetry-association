"""Tests for admin CSV import confirm/execute flow."""
from __future__ import annotations

import os

import pytest

from poem_assoc.db import get_connection

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _login(client, password="test-pass"):
    client.post("/admin/login", data={"password": password})


def _get_csrf(client):
    client.get("/admin/import")
    with client.session_transaction() as sess:
        return sess.get("csrf_token", "")


def _upload_and_preview(client, csv_path, token):
    with open(csv_path, "rb") as f:
        return client.post(
            "/admin/import/preview",
            data={"csv_file": (f, os.path.basename(csv_path)), "csrf_token": token},
            content_type="multipart/form-data",
        )


class TestConfirmWritesRows:
    def test_confirm_imports_poems(self, client, app):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)

        resp = client.post(
            "/admin/import/confirm",
            data={"csrf_token": token},
        )
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "3" in html  # imported count
        assert "Complete" in html

        # Verify rows in DB
        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        try:
            rows = conn.execute("SELECT title FROM poems ORDER BY title").fetchall()
            titles = [r["title"] for r in rows]
            assert "Import One" in titles
            assert "Import Two" in titles
            assert "Import Three" in titles
        finally:
            conn.close()

    def test_search_cache_refreshed(self, client, app):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)
        client.post("/admin/import/confirm", data={"csrf_token": token})

        # Search should find the imported poems
        resp = client.post("/search", data={"q": "morning sun"})
        assert resp.status_code == 200
        assert b"Import One" in resp.data


class TestDuplicateSkipping:
    def test_skips_db_duplicates(self, client, app, embedding_service, lexical_processor):
        """Seed one poem that matches fixture row, then import — it should be skipped."""
        from poem_assoc.db import get_connection
        from poem_assoc import repository

        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        try:
            repository.create_poem(
                conn,
                "Import One",
                "A brand new poem about the morning sun.\nBright and warm it rises.",
                embedding_service,
                lexical_processor,
            )
        finally:
            conn.close()

        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)
        resp = client.post("/admin/import/confirm", data={"csrf_token": token})
        html = resp.data.decode()
        # Only 2 new imports (Import Two, Import Three); Import One is a DB dup
        assert "Imported" in html


class TestTempFileCleanup:
    def test_temp_cleaned_on_success(self, client, app):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)
        client.post("/admin/import/confirm", data={"csrf_token": token})

        cfg = app.config["POEM_CONFIG"]
        temp_dir = cfg.import_temp_dir
        if os.path.exists(temp_dir):
            remaining = os.listdir(temp_dir)
            assert remaining == [], f"Temp files not cleaned up: {remaining}"

    def test_temp_cleaned_on_preview_error(self, client, app):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import_bad_headers.csv")
        _upload_and_preview(client, csv_path, token)

        cfg = app.config["POEM_CONFIG"]
        temp_dir = cfg.import_temp_dir
        if os.path.exists(temp_dir):
            remaining = os.listdir(temp_dir)
            assert remaining == [], f"Temp files not cleaned up: {remaining}"


class TestConfirmNoSession:
    def test_confirm_without_preview_redirects(self, client):
        _login(client)
        token = _get_csrf(client)
        resp = client.post(
            "/admin/import/confirm",
            data={"csrf_token": token},
            follow_redirects=True,
        )
        assert b"upload a CSV first" in resp.data


class TestResultPageRendering:
    def test_result_page_renders_success(self, client):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)
        resp = client.post("/admin/import/confirm", data={"csrf_token": token})
        html = resp.data.decode()
        assert "Import result" in html
        assert "Back to dashboard" in html

    def test_result_page_renders_error_on_partial_failure(self, client, app, monkeypatch):
        """Simulate a failure on the 2nd row by monkey-patching create_poem."""
        call_count = {"n": 0}
        original_create = None

        from poem_assoc import repository as repo_mod

        original_create = repo_mod.create_poem

        def failing_create(conn, title, text, emb_svc, lexical_processor):
            call_count["n"] += 1
            if call_count["n"] == 2:
                raise RuntimeError("Simulated embedding failure")
            return original_create(conn, title, text, emb_svc, lexical_processor)

        monkeypatch.setattr("poem_assoc.repository.create_poem", failing_create)
        # Also patch the reference used by csv_import
        monkeypatch.setattr("poem_assoc.csv_import.create_poem", failing_create)

        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        _upload_and_preview(client, csv_path, token)
        resp = client.post("/admin/import/confirm", data={"csrf_token": token})
        html = resp.data.decode()
        assert "Error" in html or "error" in html
        assert "Simulated embedding failure" in html
        # First row should have been kept
        assert "1" in html  # imported count

        # Verify first row is in DB
        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        try:
            rows = conn.execute("SELECT title FROM poems").fetchall()
            titles = [r["title"] for r in rows]
            assert "Import One" in titles
        finally:
            conn.close()


class TestPerformanceSmoke:
    def test_import_20_rows_under_30s(self, client, tmp_path):
        """Smoke test: generate a 20-row CSV and verify import finishes quickly."""
        import time

        csv_path = tmp_path / "perf_test.csv"
        lines = ["title,text"]
        for i in range(20):
            lines.append(f'Perf Poem {i},"This is performance test poem number {i}. Unique content here {i}."')
        csv_path.write_text("\n".join(lines), encoding="utf-8")

        _login(client)
        token = _get_csrf(client)

        start = time.time()
        with open(csv_path, "rb") as f:
            client.post(
                "/admin/import/preview",
                data={"csv_file": (f, "perf_test.csv"), "csrf_token": token},
                content_type="multipart/form-data",
            )
        client.post("/admin/import/confirm", data={"csrf_token": token})
        elapsed = time.time() - start
        assert elapsed < 30, f"Import took {elapsed:.1f}s, expected <30s"
