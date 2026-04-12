from __future__ import annotations

import sqlite3
import struct
from datetime import datetime, timezone

import numpy as np

from .embedding import EmbeddingService
from .text_cleaning import clean_poem_text, compute_dedup_key


class DuplicatePoemError(Exception):
    """Raised when attempting to insert a poem whose cleaned text already exists."""


class PoemNotFoundError(Exception):
    """Raised when a poem lookup by id fails."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_poem(
    conn: sqlite3.Connection,
    title: str,
    text: str,
    embedding_service: EmbeddingService,
) -> int:
    """Insert a poem with cleaned text and embedding. Raises DuplicatePoemError
    on duplicate cleaned text."""
    cleaned = clean_poem_text(text)
    dedup = compute_dedup_key(cleaned)

    if find_by_cleaned_text(conn, dedup) is not None:
        raise DuplicatePoemError("Duplicate poem detected (dedup key match)")

    vector = embedding_service.encode(title, cleaned)
    blob = embedding_service.to_bytes(vector)

    now = _utcnow()
    with conn:
        cursor = conn.execute(
            "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, text, dedup, blob, now, now),
        )
    return cursor.lastrowid


def get_poem(conn: sqlite3.Connection, poem_id: int) -> sqlite3.Row | None:
    """Fetch a single poem row by id."""
    return conn.execute("SELECT * FROM poems WHERE id = ?", (poem_id,)).fetchone()


_SORT_MAP: dict[str, str] = {
    "title_asc":    "title COLLATE NOCASE ASC, id ASC",
    "title_desc":   "title COLLATE NOCASE DESC, id DESC",
    "created_asc":  "created_at ASC, id ASC",
    "created_desc": "created_at DESC, id DESC",
    "updated_asc":  "updated_at ASC, id ASC",
    "updated_desc": "updated_at DESC, id DESC",
}


def list_poems(
    conn: sqlite3.Connection, order_by: str = "title_asc"
) -> list[sqlite3.Row]:
    """Return all poems ordered by the provided sort key.

    Raises ValueError for an unrecognised *order_by* value.
    """
    if order_by not in _SORT_MAP:
        raise ValueError(f"Unknown sort key: {order_by!r}")
    sql_order = _SORT_MAP[order_by]
    return conn.execute(f"SELECT * FROM poems ORDER BY {sql_order}").fetchall()


def find_by_cleaned_text(
    conn: sqlite3.Connection, dedup_key: str
) -> sqlite3.Row | None:
    """Look up a poem by its canonical dedup key stored in cleaned_text."""
    return conn.execute(
        "SELECT * FROM poems WHERE cleaned_text = ?", (dedup_key,)
    ).fetchone()


def update_poem(
    conn: sqlite3.Connection,
    poem_id: int,
    title: str,
    text: str,
    embedding_service: EmbeddingService,
) -> sqlite3.Row:
    """Update a poem's title and text, enforcing duplicate rules and
    regenerating the embedding when content changes.

    Returns the updated row.
    Raises PoemNotFoundError if the id does not exist.
    Raises DuplicatePoemError if another row has the same cleaned text.
    """
    existing = get_poem(conn, poem_id)
    if existing is None:
        raise PoemNotFoundError(f"No poem with id {poem_id}")

    cleaned = clean_poem_text(text)
    dedup = compute_dedup_key(cleaned)

    dup = find_by_cleaned_text(conn, dedup)
    if dup is not None and dup["id"] != poem_id:
        raise DuplicatePoemError("A poem with this cleaned text already exists")

    content_changed = (existing["title"] != title) or (existing["text"] != text)

    if content_changed:
        vector = embedding_service.encode(title, cleaned)
        blob = embedding_service.to_bytes(vector)
        now = _utcnow()
        with conn:
            conn.execute(
                "UPDATE poems SET title = ?, text = ?, cleaned_text = ?, "
                "embedding = ?, updated_at = ? WHERE id = ?",
                (title, text, dedup, blob, now, poem_id),
            )
    # If nothing changed, don't bump updated_at

    return get_poem(conn, poem_id)


def delete_poem(conn: sqlite3.Connection, poem_id: int) -> bool:
    """Delete a poem by id. Returns True if a row was deleted."""
    with conn:
        cursor = conn.execute("DELETE FROM poems WHERE id = ?", (poem_id,))
    return cursor.rowcount > 0


def iter_embeddings(conn: sqlite3.Connection):
    """Yield (id, title, cleaned_poem_text, vector) for every poem that has an embedding.

    The third element is derived from clean_poem_text(text) — the line-break-preserving
    form suitable for preview extraction, not the dedup key stored in cleaned_text.
    """
    rows = conn.execute(
        "SELECT id, title, text, embedding FROM poems WHERE embedding IS NOT NULL"
    ).fetchall()
    for row in rows:
        blob: bytes = row["embedding"]
        (dim,) = struct.unpack("<I", blob[:4])
        vec = np.frombuffer(blob[4:], dtype=np.float32).copy()
        yield (row["id"], row["title"], clean_poem_text(row["text"]), vec)
