"""Test helpers for building deterministic test corpora with known embedding vectors."""

from __future__ import annotations

import sqlite3
import struct

import numpy as np


def make_embedding_blob(dimension: int, index: int = 0) -> bytes:
    """Return a serialized embedding blob with a unit vector along `index`.

    All components are 0 except position `index % dimension` which is 1.0.
    This lets tests construct controlled cosine similarity outcomes.
    """
    vec = np.zeros(dimension, dtype=np.float32)
    vec[index % dimension] = 1.0
    return struct.pack("<I", dimension) + vec.tobytes()


def insert_poem_raw(
    conn: sqlite3.Connection,
    title: str,
    text: str,
    blob: bytes,
) -> int:
    """Insert a poem row directly with a pre-computed embedding blob.

    Bypasses embedding computation so tests control the exact vector.
    Returns the inserted row id.
    """
    now = "2024-01-01T00:00:00+00:00"
    cur = conn.execute(
        "INSERT INTO poems (title, text, cleaned_text, embedding, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (title, text, text, blob, now, now),
    )
    conn.commit()
    return cur.lastrowid
