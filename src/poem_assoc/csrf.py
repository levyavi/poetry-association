from __future__ import annotations

import hmac
import secrets

from flask import session


_SESSION_KEY = "csrf_token"


def issue_token() -> str:
    """Return the per-session CSRF token, creating one if absent."""
    token = session.get(_SESSION_KEY)
    if not token:
        token = secrets.token_hex(32)
        session[_SESSION_KEY] = token
    return token


def verify_token(submitted: str) -> bool:
    """Compare a form-submitted token against the session token.

    Uses constant-time comparison to prevent timing attacks.
    Returns False when either value is empty.
    """
    expected = session.get(_SESSION_KEY, "")
    if not submitted or not expected:
        return False
    return hmac.compare_digest(submitted, expected)
