from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from .index_metadata import bootstrap_index_state, ensure_metadata_table

_DDL = """
CREATE TABLE IF NOT EXISTS poems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL DEFAULT '',
    text        TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    lemmatized_search_text TEXT NOT NULL DEFAULT '',
    embedding   BLOB,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_poems_cleaned_text
    ON poems (cleaned_text);
"""


def init_db(db_path: str) -> None:
    """Create or migrate the poems schema and bootstrap search-index metadata."""
    with get_connection(db_path) as conn:
        poems_existed = _table_exists(conn, "poems")
        conn.executescript(_DDL)
        ensure_metadata_table(conn)

        migrated_legacy_index = False
        columns = _column_names(conn, "poems")
        if "lemmatized_search_text" not in columns:
            conn.execute(
                "ALTER TABLE poems ADD COLUMN "
                "lemmatized_search_text TEXT NOT NULL DEFAULT ''"
            )
            migrated_legacy_index = True

        has_poems = (
            conn.execute("SELECT EXISTS(SELECT 1 FROM poems)").fetchone()[0] == 1
        )
        bootstrap_index_state(
            conn,
            has_poems=has_poems,
            migrated_legacy_index=migrated_legacy_index and poems_existed,
            initialized_at=_utcnow(),
        )


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a configured sqlite3.Connection with row_factory and foreign keys."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _column_names(conn: sqlite3.Connection, table_name: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table_name})").fetchall()
    return {row["name"] for row in rows}


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
