"""Tests for the minimal per-session CSRF token module."""

from poem_assoc.csrf import issue_token, verify_token


def test_csrf_token_stable_in_session(app):
    """Two calls to issue_token within the same session return the same token."""
    with app.test_request_context():
        with app.test_client() as c:
            with c.session_transaction() as sess:
                pass  # ensure session exists
        # Use the request context directly
        from flask import session
        token1 = issue_token()
        token2 = issue_token()
        assert token1 == token2
        assert len(token1) == 64  # hex of 32 bytes


def test_csrf_verify_rejects_wrong_token(app):
    """verify_token returns False for incorrect or empty tokens."""
    with app.test_request_context():
        from flask import session
        token = issue_token()
        assert verify_token(token) is True
        assert verify_token("wrong-token") is False
        assert verify_token("") is False


def test_csrf_verify_rejects_empty_session(app):
    """verify_token returns False when no token has been issued."""
    with app.test_request_context():
        assert verify_token("anything") is False
