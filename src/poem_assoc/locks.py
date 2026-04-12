from __future__ import annotations

import threading


class RebuildLock:
    """Process-wide exclusive lock for the embedding rebuild operation.

    Only one rebuild can run at a time. The lock exposes a non-blocking
    ``acquire`` and a boolean ``is_rebuilding`` probe that routes can
    check without attempting to take the lock.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rebuilding = False

    def acquire(self) -> bool:
        """Try to acquire the rebuild lock (non-blocking).

        Returns True on success, False if the lock is already held.
        """
        got = self._lock.acquire(blocking=False)
        if got:
            self._rebuilding = True
        return got

    def release(self) -> None:
        """Release the lock and clear the rebuilding flag.

        Safe to call even if the lock is not currently held.
        """
        self._rebuilding = False
        try:
            self._lock.release()
        except RuntimeError:
            # Already released — silently ignore.
            pass

    def is_rebuilding(self) -> bool:
        """Return whether a rebuild is currently in progress."""
        return self._rebuilding

    def __enter__(self) -> RebuildLock:
        if not self.acquire():
            raise RuntimeError("Rebuild lock is already held")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.release()
