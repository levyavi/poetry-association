from __future__ import annotations

import sqlite3

from poem_assoc.constants import (
    LEGACY_SEARCH_INDEX_VERSION,
    SCHEMA_VERSION,
    SEARCH_INDEX_VERSION,
)
from poem_assoc.db import get_connection, init_db
from poem_assoc.index_metadata import get_index_state, mark_rebuild_success


def _create_v1_schema(db_path: str) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(
            """
            CREATE TABLE poems (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL DEFAULT '',
                text TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                embedding BLOB,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at)
            VALUES ('Legacy', 'Leaves were falling', 'Leaves were falling', NULL,
                    '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00');
            """
        )
        conn.commit()
    finally:
        conn.close()


def test_get_index_state_distinguishes_fresh_v2_and_migrated_v1(temp_db_path):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        state = get_index_state(conn)
        assert state.schema_version == SCHEMA_VERSION
        assert state.search_index_version == SEARCH_INDEX_VERSION
        assert state.is_current()
        assert state.last_successful_full_rebuild_at is not None
    finally:
        conn.close()

    legacy_path = temp_db_path + ".legacy"
    _create_v1_schema(legacy_path)
    init_db(legacy_path)
    conn = get_connection(legacy_path)
    try:
        columns = {
            row["name"] for row in conn.execute("PRAGMA table_info(poems)").fetchall()
        }
        row_count = conn.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
        state = get_index_state(conn)

        assert "lemmatized_search_text" in columns
        assert row_count == 1
        assert state.schema_version == SCHEMA_VERSION
        assert state.search_index_version == LEGACY_SEARCH_INDEX_VERSION
        assert not state.is_current()
    finally:
        conn.close()


def test_app_metadata_rows_written_on_full_rebuild_success(temp_db_path):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        mark_rebuild_success(conn, SEARCH_INDEX_VERSION, "2024-02-02T00:00:00+00:00")
        state = get_index_state(conn)
        assert state.schema_version == SCHEMA_VERSION
        assert state.search_index_version == SEARCH_INDEX_VERSION
        assert state.last_successful_full_rebuild_at == "2024-02-02T00:00:00+00:00"
    finally:
        conn.close()
