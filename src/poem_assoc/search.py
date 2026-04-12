from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from . import constants
from . import repository
from .db import get_connection
from .embedding import EmbeddingService
from .text_cleaning import clean_query


@dataclass(frozen=True)
class SearchResult:
    """Immutable value type returned to templates."""

    id: int
    title: str
    preview: str
    score: float
    label: str


def _make_preview(text: str) -> str:
    """Return the first two non-empty lines of text.

    Appends an ellipsis (…) suffix when the text has more than two non-empty lines.
    """
    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) <= 2:
        return "\n".join(lines)
    return "\n".join(lines[:2]) + "\u2026"


class SearchService:
    """Owns the in-memory embedding cache and runs cosine similarity ranking."""

    def __init__(self, db_path: str, embedding_service: EmbeddingService) -> None:
        self._db_path = db_path
        self._embedding_service = embedding_service
        self._lock = threading.Lock()
        self._cached = False
        self._ids: list[int] = []
        self._titles: list[str] = []
        self._cleaned_texts: list[str] = []
        self._matrix: np.ndarray = np.empty((0, 0), dtype=np.float32)

    def _load_cache(self) -> None:
        """Load all embeddings from the DB into the in-memory matrix.

        Must be called while holding self._lock.
        """
        conn = get_connection(self._db_path)
        try:
            rows = list(repository.iter_embeddings(conn))
        finally:
            conn.close()

        if not rows:
            self._ids = []
            self._titles = []
            self._cleaned_texts = []
            self._matrix = np.empty((0, 0), dtype=np.float32)
        else:
            ids, titles, cleaned_texts, vectors = zip(*rows)
            self._ids = list(ids)
            self._titles = list(titles)
            self._cleaned_texts = list(cleaned_texts)
            self._matrix = np.stack(vectors, axis=0).astype(np.float32)

        self._cached = True

    def refresh(self) -> None:
        """Invalidate and rebuild the in-memory embedding cache."""
        with self._lock:
            self._cached = False
            self._load_cache()

    def search(self, query: str, limit: int = 5) -> list[SearchResult]:
        """Return the top `limit` results for a query, sorted by cosine similarity.

        Returns an empty list when the query is empty or the DB has no poems.
        Ties in cosine score are broken by title ASC.
        """
        cleaned = clean_query(query)
        if not cleaned:
            return []

        with self._lock:
            if not self._cached:
                self._load_cache()

            if self._matrix.shape[0] == 0:
                return []

            query_vector = self._embedding_service.encode_query(cleaned)
            scores = self._matrix @ query_vector

            ranked = sorted(
                zip(scores.tolist(), self._titles, self._ids, self._cleaned_texts),
                key=lambda x: (-x[0], x[1]),
            )

            results: list[SearchResult] = []
            for score, title, poem_id, cleaned_text in ranked[:limit]:
                display_title = title if title else "Untitled"
                preview = _make_preview(cleaned_text)
                label = constants.label_for(score)
                results.append(
                    SearchResult(
                        id=poem_id,
                        title=display_title,
                        preview=preview,
                        score=score,
                        label=label,
                    )
                )

            return results
