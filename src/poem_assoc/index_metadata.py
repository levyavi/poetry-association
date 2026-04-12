from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .constants import (
    LEGACY_SEARCH_INDEX_VERSION,
    SCHEMA_VERSION,
    SEARCH_INDEX_VERSION,
)

_METADATA_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS app_metadata (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class SearchIndexState:
    """Persistent compatibility state for schema and derived lexical search data."""

    schema_version: str
    search_index_version: str
    last_successful_full_rebuild_at: str | None

    def is_current(self) -> bool:
        return self.search_index_version == SEARCH_INDEX_VERSION


def ensure_metadata_table(conn: sqlite3.Connection) -> None:
    """Create the metadata table idempotently."""
    conn.execute(_METADATA_TABLE_DDL)


def get_index_state(conn: sqlite3.Connection) -> SearchIndexState:
    """Read the current persisted search-index compatibility metadata."""
    ensure_metadata_table(conn)
    rows = conn.execute(
        "SELECT key, value FROM app_metadata "
        "WHERE key IN ('schema_version', 'search_index_version', "
        "'last_successful_full_rebuild_at')"
    ).fetchall()
    values = {row["key"]: row["value"] for row in rows}
    rebuilt_at = values.get("last_successful_full_rebuild_at") or None
    return SearchIndexState(
        schema_version=values.get("schema_version", ""),
        search_index_version=values.get("search_index_version", ""),
        last_successful_full_rebuild_at=rebuilt_at,
    )


def mark_rebuild_success(
    conn: sqlite3.Connection,
    search_index_version: str,
    rebuilt_at: str,
) -> None:
    """Persist successful full-rebuild metadata for the active index version."""
    _set_metadata_values(
        conn,
        {
            "schema_version": SCHEMA_VERSION,
            "search_index_version": search_index_version,
            "last_successful_full_rebuild_at": rebuilt_at,
        },
    )


def bootstrap_index_state(
    conn: sqlite3.Connection,
    *,
    has_poems: bool,
    migrated_legacy_index: bool,
    initialized_at: str,
) -> None:
    """Initialize metadata for fresh DBs or V1 migrations without clobbering current state."""
    state = get_index_state(conn)
    updates: dict[str, str] = {}

    if state.schema_version != SCHEMA_VERSION:
        updates["schema_version"] = SCHEMA_VERSION

    if migrated_legacy_index:
        updates["search_index_version"] = LEGACY_SEARCH_INDEX_VERSION
        if state.last_successful_full_rebuild_at is None:
            updates["last_successful_full_rebuild_at"] = ""
    elif not state.search_index_version:
        if has_poems:
            updates["search_index_version"] = LEGACY_SEARCH_INDEX_VERSION
            updates["last_successful_full_rebuild_at"] = ""
        else:
            updates["search_index_version"] = SEARCH_INDEX_VERSION
            updates["last_successful_full_rebuild_at"] = initialized_at
    elif state.is_current() and state.last_successful_full_rebuild_at is None:
        updates["last_successful_full_rebuild_at"] = initialized_at

    if updates:
        _set_metadata_values(conn, updates)


def _set_metadata_values(
    conn: sqlite3.Connection,
    metadata: dict[str, str],
) -> None:
    with conn:
        conn.executemany(
            "INSERT INTO app_metadata (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            list(metadata.items()),
        )
