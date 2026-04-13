"""Tests for admin CSV import upload and preview."""
from __future__ import annotations

import io
import os

import pytest


FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def _login(client, password="test-pass"):
    client.post("/admin/login", data={"password": password})


def _get_csrf(client):
    """Fetch a page to seed the session, then extract the CSRF token."""
    with client.session_transaction() as sess:
        if "csrf_token" not in sess:
            # Hit any authed page to seed csrf
            pass
    # Just issue a GET to seed the session
    client.get("/admin/import")
    with client.session_transaction() as sess:
        return sess.get("csrf_token", "")


def _upload(client, csv_path, csrf_token):
    with open(csv_path, "rb") as f:
        data = {
            "csv_file": (f, os.path.basename(csv_path)),
            "csrf_token": csrf_token,
        }
        return client.post(
            "/admin/import/preview",
            data=data,
            content_type="multipart/form-data",
        )


class TestImportPreviewCounts:
    def test_valid_csv_shows_counts(self, client):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        resp = _upload(client, csv_path, token)
        assert resp.status_code == 200
        html = resp.data.decode()
        assert "5" in html  # importable count
        assert "0" in html  # duplicate count
        assert "fixture_import.csv" in html

    def test_preview_page_renders_counts(self, client):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        resp = _upload(client, csv_path, token)
        html = resp.data.decode()
        assert "Rows to import" in html
        assert "Duplicates to skip" in html
        assert "Confirm import" in html


class TestBadHeaders:
    def test_bad_headers_rejected(self, client, app):
        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import_bad_headers.csv")
        resp = _upload(client, csv_path, token)
        assert resp.status_code == 422
        html = resp.data.decode()
        assert "headers" in html.lower()

        # Verify no temp files remain
        cfg = app.config["POEM_CONFIG"]
        temp_dir = cfg.import_temp_dir
        if os.path.exists(temp_dir):
            remaining = os.listdir(temp_dir)
            assert remaining == [], f"Temp files not cleaned up: {remaining}"

    def test_no_file_selected(self, client):
        _login(client)
        token = _get_csrf(client)
        resp = client.post(
            "/admin/import/preview",
            data={"csrf_token": token},
            content_type="multipart/form-data",
        )
        assert resp.status_code == 422
        assert b"No file selected" in resp.data


class TestAuthAndCsrf:
    def test_preview_requires_auth(self, client):
        resp = client.post("/admin/import/preview", data={})
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_confirm_requires_auth(self, client):
        resp = client.post("/admin/import/confirm", data={})
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_cancel_requires_auth(self, client):
        resp = client.post("/admin/import/cancel", data={})
        assert resp.status_code == 302
        assert "/admin/login" in resp.headers["Location"]

    def test_preview_requires_csrf(self, client):
        _login(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")
        with open(csv_path, "rb") as f:
            resp = client.post(
                "/admin/import/preview",
                data={"csv_file": (f, "import.csv")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 400

    def test_confirm_requires_csrf(self, client):
        _login(client)
        resp = client.post("/admin/import/confirm", data={})
        assert resp.status_code == 400
