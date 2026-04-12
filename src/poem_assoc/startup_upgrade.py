from __future__ import annotations

import threading
from dataclasses import dataclass

from .db import get_connection
from .embedding import EmbeddingService
from .index_metadata import get_index_state
from .lexical import LexicalTextProcessor
from .locks import RebuildLock
from .rebuild import run_rebuild
from .search import SearchService

_RUNNING_DETAIL = "Search data is being upgraded. Search is temporarily unavailable."


@dataclass(frozen=True)
class UpgradeStatus:
    """Process-local availability state for the startup search-data upgrade."""

    state: str
    detail: str | None = None

    @classmethod
    def idle(cls) -> "UpgradeStatus":
        return cls("idle")

    @classmethod
    def ready(cls) -> "UpgradeStatus":
        return cls("ready")

    @classmethod
    def running(cls) -> "UpgradeStatus":
        return cls("running", _RUNNING_DETAIL)

    @classmethod
    def failed(cls, detail: str) -> "UpgradeStatus":
        return cls("failed", detail)

    def is_search_available(self) -> bool:
        return self.state in {"idle", "ready"}

    def is_write_available(self) -> bool:
        return self.state in {"idle", "ready"}


class StartupUpgradeCoordinator:
    """Run at most one automatic startup rebuild when persisted search data is outdated."""

    def __init__(
        self,
        db_path: str,
        embedding_service: EmbeddingService,
        lexical_processor: LexicalTextProcessor,
        search_service: SearchService,
        rebuild_lock: RebuildLock,
    ) -> None:
        self._db_path = db_path
        self._embedding_service = embedding_service
        self._lexical_processor = lexical_processor
        self._search_service = search_service
        self._rebuild_lock = rebuild_lock
        self._state_lock = threading.Lock()
        self._status = UpgradeStatus.idle()
        self._started = False
        self._thread: threading.Thread | None = None

    def begin_if_needed(self) -> bool:
        """Start the background startup rebuild exactly once when metadata is outdated."""
        with self._state_lock:
            if self._started:
                return False
            self._started = True

        try:
            if not self.requires_rebuild():
                self.mark_ready()
                return False
        except Exception as exc:
            self.mark_failed(
                f"Automatic startup upgrade could not inspect the search index: {exc}"
            )
            return False

        if not self._rebuild_lock.acquire():
            self.mark_failed(
                "Automatic startup upgrade could not begin because another rebuild is already running."
            )
            return False

        thread = threading.Thread(
            target=self.run,
            name="startup-upgrade-rebuild",
            daemon=True,
        )
        with self._state_lock:
            self._status = UpgradeStatus.running()
            self._thread = thread

        try:
            thread.start()
        except Exception as exc:
            self._rebuild_lock.release()
            self.mark_failed(f"Automatic startup upgrade could not start: {exc}")
            return False

        return True

    def status(self) -> UpgradeStatus:
        """Return the current startup-upgrade status."""
        with self._state_lock:
            return self._status

    def requires_rebuild(self) -> bool:
        """Return True when persisted search data is older than the running app version."""
        conn = get_connection(self._db_path)
        try:
            return not get_index_state(conn).is_current()
        finally:
            conn.close()

    def mark_ready(self) -> None:
        with self._state_lock:
            self._status = UpgradeStatus.ready()

    def mark_failed(self, detail: str) -> None:
        with self._state_lock:
            self._status = UpgradeStatus.failed(detail)

    def run(self) -> None:
        """Execute the automatic startup rebuild and update process-local availability state."""
        try:
            conn = get_connection(self._db_path)
            try:
                result = run_rebuild(
                    conn,
                    self._embedding_service,
                    self._lexical_processor,
                )
            finally:
                conn.close()

            if result.succeeded:
                self._search_service.refresh()
                self.mark_ready()
                return

            self.mark_failed(
                f"Automatic startup upgrade failed after {result.rebuilt}/{result.total} poems: {result.error}"
            )
        except Exception as exc:
            self.mark_failed(f"Automatic startup upgrade failed: {exc}")
        finally:
            self._rebuild_lock.release()
