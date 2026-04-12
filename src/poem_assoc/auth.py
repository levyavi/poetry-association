from __future__ import annotations

import hmac
from functools import wraps

from flask import current_app, redirect, session, url_for


_SESSION_KEY = "admin_authenticated"


def is_authenticated() -> bool:
    """Return True when the current session is marked as admin-authenticated."""
    return session.get(_SESSION_KEY) is True


def login() -> None:
    """Mark the current session as authenticated; expires on browser close."""
    session.permanent = False
    session[_SESSION_KEY] = True


def logout() -> None:
    """Remove the authentication flag from the current session."""
    session.pop(_SESSION_KEY, None)


def verify_password(submitted: str) -> bool:
    """Compare *submitted* against the configured admin password using a
    constant-time comparison to prevent timing attacks."""
    cfg = current_app.config["POEM_CONFIG"]
    configured: str = cfg.admin_password
    return hmac.compare_digest(
        submitted.encode("utf-8"), configured.encode("utf-8")
    )


def login_required(view):
    """Decorator that redirects unauthenticated requests to /admin/login."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not is_authenticated():
            return redirect(url_for("admin.login_view"))
        return view(*args, **kwargs)
    return wrapped
