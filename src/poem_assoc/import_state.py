from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

from .csv_import import ImportPlan


@dataclass
class ImportSession:
    """Bundle of state for one in-progress admin CSV import."""

    session_id: str
    plan: ImportPlan
    temp_path: str
    filename: str
    created_at: float = field(default_factory=time.time)
    _cancel_event: threading.Event = field(default_factory=threading.Event)

    def cancel(self) -> None:
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def cleanup(self) -> None:
        """Remove the temp file if it still exists."""
        try:
            os.unlink(self.temp_path)
        except FileNotFoundError:
            pass


_sessions: dict[str, ImportSession] = {}
_lock = threading.Lock()


def create(
    session_id: str,
    plan: ImportPlan,
    temp_path: str,
    filename: str,
) -> ImportSession:
    """Create an ImportSession, replacing any previous one for this session id."""
    with _lock:
        old = _sessions.pop(session_id, None)
    if old is not None:
        old.cleanup()

    sess = ImportSession(
        session_id=session_id,
        plan=plan,
        temp_path=temp_path,
        filename=filename,
    )
    with _lock:
        _sessions[session_id] = sess
    return sess


def get(session_id: str) -> ImportSession | None:
    with _lock:
        return _sessions.get(session_id)


def cancel(session_id: str) -> bool:
    """Set the cancel flag. Returns True if a session existed."""
    sess = get(session_id)
    if sess is None:
        return False
    sess.cancel()
    return True


def discard(session_id: str) -> None:
    """Remove the session and delete its temp file. Idempotent."""
    with _lock:
        sess = _sessions.pop(session_id, None)
    if sess is not None:
        sess.cleanup()


def cleanup_expired(max_age_seconds: int = 3600) -> None:
    """Remove sessions older than *max_age_seconds* and delete their temp files."""
    now = time.time()
    expired: list[ImportSession] = []
    with _lock:
        for sid in list(_sessions):
            sess = _sessions[sid]
            if now - sess.created_at > max_age_seconds:
                expired.append(_sessions.pop(sid))

    for sess in expired:
        sess.cleanup()
