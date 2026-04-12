"""Tests for admin CSV import cancellation and import_state module."""
from __future__ import annotations

import os
import threading
import time

import pytest

from poem_assoc import import_state
from poem_assoc.csv_import import ImportPlan, PlannedRow


class TestImportSessionCancelFlag:
    def test_cancel_sets_event(self):
        sess = import_state.ImportSession(
            session_id="test",
            plan=ImportPlan(),
            temp_path="/nonexistent",
            filename="test.csv",
        )
        assert not sess.is_cancelled()
        sess.cancel()
        assert sess.is_cancelled()


class TestImportStateDiscard:
    def test_discard_removes_temp_file(self, tmp_path):
        temp_file = tmp_path / "temp.csv"
        temp_file.write_text("title,text\n")

        import_state.create("sid1", ImportPlan(), str(temp_file), "test.csv")
        assert temp_file.exists()

        import_state.discard("sid1")
        assert not temp_file.exists()
        assert import_state.get("sid1") is None

    def test_discard_idempotent(self):
        import_state.discard("nonexistent-sid")  # should not raise


class TestCleanupExpired:
    def test_removes_old_sessions(self, tmp_path):
        temp_file = tmp_path / "old.csv"
        temp_file.write_text("title,text\n")

        sess = import_state.create("old-sid", ImportPlan(), str(temp_file), "old.csv")
        # Backdate the session
        sess.created_at = time.time() - 7200

        import_state.cleanup_expired(max_age_seconds=3600)
        assert import_state.get("old-sid") is None
        assert not temp_file.exists()

    def test_keeps_recent_sessions(self, tmp_path):
        temp_file = tmp_path / "recent.csv"
        temp_file.write_text("title,text\n")

        import_state.create("recent-sid", ImportPlan(), str(temp_file), "recent.csv")
        import_state.cleanup_expired(max_age_seconds=3600)
        assert import_state.get("recent-sid") is not None

        # Clean up
        import_state.discard("recent-sid")


class TestCancelMidImport:
    def test_cancel_preserves_prior_rows(self, app, embedding_service):
        """Start an import in a thread, cancel after ~1 row, verify partial preservation."""
        from poem_assoc.db import get_connection, init_db
        from poem_assoc import csv_import

        cfg = app.config["POEM_CONFIG"]
        conn = get_connection(cfg.db_path)
        lexical_processor = app.extensions["lexical"]

        # Build a plan with 5 rows
        rows = []
        for i in range(5):
            rows.append(PlannedRow(
                title=f"Cancel Test {i}",
                text=f"Unique cancel test poem number {i} with special content.",
                cleaned_text=f"unique cancel test poem number {i} with special content.",
                dedup_key=f"unique cancel test poem number {i} with special content.",
            ))
        plan = ImportPlan(importable_rows=rows, duplicate_count=0)

        cancel_event = threading.Event()
        call_count = {"n": 0}

        def cancel_flag():
            return cancel_event.is_set()

        def on_progress(done, total):
            call_count["n"] = done
            if done >= 2:
                cancel_event.set()

        try:
            result = csv_import.execute(
                conn, plan, embedding_service, lexical_processor,
                cancel_flag=cancel_flag,
                on_progress=on_progress,
            )
        finally:
            conn.close()

        assert result.cancelled is True
        assert result.imported >= 2
        assert result.imported < 5

        # Verify rows are actually in DB
        conn2 = get_connection(cfg.db_path)
        try:
            count = conn2.execute(
                "SELECT COUNT(*) as c FROM poems WHERE title LIKE 'Cancel Test%'"
            ).fetchone()["c"]
            assert count == result.imported
        finally:
            conn2.close()


class TestResultPageCancelledState:
    def test_result_shows_cancelled(self, client):
        """Render the result page with a cancelled result via a real import flow."""
        from poem_assoc import csv_import

        # We'll use the on_progress hook to cancel after the first row
        FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")

        def _login(c):
            c.post("/admin/login", data={"password": "test-pass"})

        def _get_csrf(c):
            c.get("/admin/import")
            with c.session_transaction() as sess:
                return sess.get("csrf_token", "")

        _login(client)
        token = _get_csrf(client)
        csv_path = os.path.join(FIXTURE_DIR, "fixture_import.csv")

        with open(csv_path, "rb") as f:
            client.post(
                "/admin/import/preview",
                data={"csv_file": (f, "fixture_import.csv"), "csrf_token": token},
                content_type="multipart/form-data",
            )

        # Set the cancel flag on the import session before confirming
        with client.session_transaction() as sess:
            sid = sess.get("_import_sid")

        if sid:
            import_state.cancel(sid)

        resp = client.post("/admin/import/confirm", data={"csrf_token": token})
        html = resp.data.decode()
        assert "Cancelled" in html or "cancelled" in html.lower()
