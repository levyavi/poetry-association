from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .embedding import EmbeddingService
from .text_cleaning import clean_poem_text


@dataclass
class RebuildResult:
    """Outcome of a full embedding rebuild."""

    total: int
    rebuilt: int
    error: str | None = None


def run_rebuild(
    conn: sqlite3.Connection,
    embedding_service: EmbeddingService,
) -> RebuildResult:
    """Re-encode every poem's embedding and commit each row individually.

    Returns a ``RebuildResult`` with counts. On a per-row failure the
    already-committed rows keep their new embeddings and the error is
    recorded in the result (partial progress is preserved).
    """
    rows = conn.execute(
        "SELECT id, title, text FROM poems ORDER BY id"
    ).fetchall()

    total = len(rows)
    rebuilt = 0

    for row in rows:
        poem_id = row["id"]
        title = row["title"]
        text = row["text"]

        try:
            cleaned = clean_poem_text(text)
            vector = embedding_service.encode(title, cleaned)
            blob = embedding_service.to_bytes(vector)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            with conn:
                conn.execute(
                    "UPDATE poems SET embedding = ?, updated_at = ? WHERE id = ?",
                    (blob, now, poem_id),
                )
            rebuilt += 1
        except Exception as exc:
            return RebuildResult(total=total, rebuilt=rebuilt, error=str(exc))

    return RebuildResult(total=total, rebuilt=rebuilt)
