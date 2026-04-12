"""Unit tests for auth helpers and repository sort behaviour."""
import pytest

from poem_assoc import auth, repository
from poem_assoc.db import get_connection, init_db


# ---------------------------------------------------------------------------
# repository.list_poems — sort validation
# ---------------------------------------------------------------------------

class TestListPoemsSort:
    def test_rejects_unknown_sort(self, db_conn):
        with pytest.raises(ValueError, match="Unknown sort key"):
            repository.list_poems(db_conn, order_by="bogus_key")

    def test_title_asc_case_insensitive(self, db_conn):
        """Inserting Zebra, apple, Apple returns apple, Apple, Zebra (COLLATE NOCASE, then id)."""
        now = "2024-01-01T00:00:00+00:00"
        db_conn.execute(
            "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
            "VALUES (?, '', '', NULL, ?, ?)",
            ("Zebra", now, now),
        )
        db_conn.execute(
            "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
            "VALUES (?, '', '', NULL, ?, ?)",
            ("apple", now, now),
        )
        db_conn.execute(
            "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
            "VALUES (?, '', '', NULL, ?, ?)",
            ("Apple", now, now),
        )
        db_conn.commit()

        rows = repository.list_poems(db_conn, order_by="title_asc")
        titles = [r["title"] for r in rows]
        # COLLATE NOCASE treats apple == Apple, so they're sorted by id (insertion order)
        assert titles == ["apple", "Apple", "Zebra"]


# ---------------------------------------------------------------------------
# auth module — password verification
# ---------------------------------------------------------------------------

class TestVerifyPassword:
    def test_correct_password_returns_true(self, app):
        with app.test_request_context():
            assert auth.verify_password("test-pass") is True

    def test_wrong_password_returns_false(self, app):
        with app.test_request_context():
            assert auth.verify_password("wrong") is False

    def test_empty_submitted_returns_false(self, app):
        with app.test_request_context():
            assert auth.verify_password("") is False

    def test_case_sensitive(self, app):
        with app.test_request_context():
            assert auth.verify_password("TEST-PASS") is False


# ---------------------------------------------------------------------------
# auth module — session helpers
# ---------------------------------------------------------------------------

class TestSessionHelpers:
    def test_is_authenticated_false_by_default(self, app):
        with app.test_request_context():
            from flask import session
            with app.test_client() as c:
                with c.session_transaction() as sess:
                    assert sess.get("admin_authenticated") is None

    def test_login_sets_flag(self, app):
        with app.test_client() as c:
            with app.test_request_context():
                from flask import session
                with c.application.test_request_context():
                    # Use the session cookie directly via the test client
                    pass
            # Verify via a round-trip: POST /admin/login sets the cookie
            resp = c.post("/admin/login", data={"password": "test-pass"})
            assert resp.status_code == 302
            resp2 = c.get("/admin/")
            assert resp2.status_code == 200

    def test_logout_clears_flag(self, app):
        with app.test_client() as c:
            c.post("/admin/login", data={"password": "test-pass"})
            c.post("/admin/logout")
            resp = c.get("/admin/")
            assert resp.status_code == 302
