from __future__ import annotations

import sqlite3


_DDL = """
CREATE TABLE IF NOT EXISTS poems (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL DEFAULT '',
    text        TEXT NOT NULL,
    cleaned_text TEXT NOT NULL,
    embedding   BLOB,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_poems_cleaned_text
    ON poems (cleaned_text);
"""


def init_db(db_path: str) -> None:
    """Create the poems table and supporting index idempotently."""
    with get_connection(db_path) as conn:
        conn.executescript(_DDL)


def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a configured sqlite3.Connection with row_factory and foreign keys."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn
