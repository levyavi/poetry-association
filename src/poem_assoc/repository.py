from __future__ import annotations

import sqlite3
import struct
from datetime import datetime, timezone

import numpy as np

from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor
from .text_cleaning import clean_poem_text


class DuplicatePoemError(Exception):
    """Raised when attempting to insert a poem whose title+body already exists."""


class PoemNotFoundError(Exception):
    """Raised when a poem lookup by id fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_required_title(title: str) -> str:
    """Return a trimmed title or raise when it is blank."""
    normalized = (title or "").strip()
    if not normalized:
        raise ValueError("Poem title is required")
    return normalized


def find_by_title_and_cleaned_text(
    conn: sqlite3.Connection, title: str, cleaned_text: str
) -> sqlite3.Row | None:
    """Look up a poem by normalized title and cleaned body text."""
    return conn.execute(
        "SELECT * FROM poems WHERE title = ? AND cleaned_text = ?",
        (title, cleaned_text),
    ).fetchone()


def create_poem(
    conn: sqlite3.Connection,
    title: str,
    text: str,
    embedding_service: EmbeddingService,
    lexical_processor: LexicalTextProcessor,
) -> int:
    """Insert a poem with cleaned text, lexical text, and embedding."""
    title = _normalize_required_title(title)
    cleaned = clean_poem_text(text)

    if find_by_title_and_cleaned_text(conn, title, cleaned) is not None:
        raise DuplicatePoemError("Duplicate poem detected (matching title and text)")

    search_text = lexical_processor.build_search_text(title, text)
    vector = embedding_service.encode(title, cleaned)
    blob = embedding_service.to_bytes(vector)

    now = _utcnow()
    with conn:
        cursor = conn.execute(
            "INSERT INTO poems "
            "(title, text, cleaned_text, lemmatized_search_text, embedding, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (title, text, cleaned, search_text, blob, now, now),
        )
    return cursor.lastrowid


def get_poem(conn: sqlite3.Connection, poem_id: int) -> sqlite3.Row | None:
    """Fetch a single poem row by id."""
    return conn.execute("SELECT * FROM poems WHERE id = ?", (poem_id,)).fetchone()


_SORT_MAP: dict[str, str] = {
    "title_asc": "title COLLATE NOCASE ASC, id ASC",
    "title_desc": "title COLLATE NOCASE DESC, id DESC",
    "created_asc": "created_at ASC, id ASC",
    "created_desc": "created_at DESC, id DESC",
    "updated_asc": "updated_at ASC, id ASC",
    "updated_desc": "updated_at DESC, id DESC",
}


def list_poems(
    conn: sqlite3.Connection, order_by: str = "title_asc"
) -> list[sqlite3.Row]:
    """Return all poems ordered by the provided sort key."""
    if order_by not in _SORT_MAP:
        raise ValueError(f"Unknown sort key: {order_by!r}")
    sql_order = _SORT_MAP[order_by]
    return conn.execute(f"SELECT * FROM poems ORDER BY {sql_order}").fetchall()


def find_by_cleaned_text(
    conn: sqlite3.Connection, dedup_key: str
) -> sqlite3.Row | None:
    """Look up a poem by its normalized body text stored in cleaned_text."""
    return conn.execute(
        "SELECT * FROM poems WHERE cleaned_text = ?", (dedup_key,)
    ).fetchone()


def update_poem(
    conn: sqlite3.Connection,
    poem_id: int,
    title: str,
    text: str,
    embedding_service: EmbeddingService,
    lexical_processor: LexicalTextProcessor,
) -> sqlite3.Row:
    """Update a poem's title and text, regenerating all derived fields."""
    existing = get_poem(conn, poem_id)
    if existing is None:
        raise PoemNotFoundError(f"No poem with id {poem_id}")

    title = _normalize_required_title(title)
    cleaned = clean_poem_text(text)

    dup = find_by_title_and_cleaned_text(conn, title, cleaned)
    if dup is not None and dup["id"] != poem_id:
        raise DuplicatePoemError("A poem with this title and text already exists")

    content_changed = (existing["title"] != title) or (existing["text"] != text)

    if content_changed:
        search_text = lexical_processor.build_search_text(title, text)
        vector = embedding_service.encode(title, cleaned)
        blob = embedding_service.to_bytes(vector)
        now = _utcnow()
        with conn:
            conn.execute(
                "UPDATE poems SET title = ?, text = ?, cleaned_text = ?, "
                "lemmatized_search_text = ?, embedding = ?, updated_at = ? WHERE id = ?",
                (title, text, cleaned, search_text, blob, now, poem_id),
            )
    # If nothing changed, don't bump updated_at

    return get_poem(conn, poem_id)


def delete_poem(conn: sqlite3.Connection, poem_id: int) -> bool:
    """Delete a poem by id. Returns True if a row was deleted."""
    with conn:
        cursor = conn.execute("DELETE FROM poems WHERE id = ?", (poem_id,))
    return cursor.rowcount > 0


def iter_embeddings(conn: sqlite3.Connection):
    """Yield lexical and embedding search data for every poem that has an embedding."""
    rows = conn.execute(
        "SELECT id, title, text, lemmatized_search_text, embedding "
        "FROM poems WHERE embedding IS NOT NULL ORDER BY id"
    ).fetchall()
    for row in rows:
        blob: bytes = row["embedding"]
        (dim,) = struct.unpack("<I", blob[:4])
        vec = np.frombuffer(blob[4:], dtype=np.float32).copy()
        if len(vec) != dim:
            raise ValueError(f"Embedding blob dimension mismatch for poem {row['id']}")
        yield (
            row["id"],
            row["title"],
            clean_poem_text(row["text"]),
            row["lemmatized_search_text"] or "",
            vec,
        )
