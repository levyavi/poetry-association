from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone

from .constants import SEARCH_INDEX_VERSION
from .embedding import EmbeddingService
from .index_metadata import mark_rebuild_success
from .lexical import LexicalTextProcessor
from .text_cleaning import clean_poem_text, compute_dedup_key


@dataclass
class RebuildResult:
    """Outcome of a full embedding rebuild."""

    total: int
    rebuilt: int
    error: str | None = None
    rebuilt_at: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def run_rebuild(
    conn: sqlite3.Connection,
    embedding_service: EmbeddingService,
    lexical_processor: LexicalTextProcessor,
) -> RebuildResult:
    """Recompute all derived search data row-by-row, preserving partial progress."""
    rows = conn.execute("SELECT id, title, text FROM poems ORDER BY id").fetchall()

    total = len(rows)
    rebuilt = 0

    for row in rows:
        poem_id = row["id"]
        title = row["title"]
        text = row["text"]

        try:
            cleaned = clean_poem_text(text)
            dedup = compute_dedup_key(cleaned)
            search_text = lexical_processor.build_search_text(title, text)
            vector = embedding_service.encode(title, cleaned)
            blob = embedding_service.to_bytes(vector)
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")

            with conn:
                conn.execute(
                    "UPDATE poems SET cleaned_text = ?, lemmatized_search_text = ?, "
                    "embedding = ?, updated_at = ? WHERE id = ?",
                    (dedup, search_text, blob, now, poem_id),
                )
            rebuilt += 1
        except Exception as exc:
            return RebuildResult(total=total, rebuilt=rebuilt, error=str(exc))

    rebuilt_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    mark_rebuild_success(conn, SEARCH_INDEX_VERSION, rebuilt_at)
    return RebuildResult(total=total, rebuilt=rebuilt, rebuilt_at=rebuilt_at)
