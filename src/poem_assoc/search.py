from __future__ import annotations

import threading
from dataclasses import dataclass

import numpy as np

from . import constants
from . import repository
from .db import get_connection
from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor
from .text_cleaning import clean_query


@dataclass(frozen=True)
class SearchResult:
    """Immutable value type returned to templates."""

    id: int
    title: str
    preview: str
    semantic_score: float
    lexical_score: float
    final_score: float
    label: str

    @property
    def score(self) -> float:
        """Backward-compatible alias for templates/tests that read result.score."""
        return self.final_score


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

    def __init__(
        self,
        db_path: str,
        embedding_service: EmbeddingService,
        lexical_processor: LexicalTextProcessor,
    ) -> None:
        self._db_path = db_path
        self._embedding_service = embedding_service
        self._lexical_processor = lexical_processor
        self._lock = threading.Lock()
        self._cached = False
        self._ids: list[int] = []
        self._titles: list[str] = []
        self._cleaned_texts: list[str] = []
        self._lexical_terms: list[frozenset[str]] = []
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
            self._lexical_terms = []
            self._matrix = np.empty((0, 0), dtype=np.float32)
        else:
            ids, titles, cleaned_texts, lexical_texts, vectors = zip(*rows)
            self._ids = list(ids)
            self._titles = list(titles)
            self._cleaned_texts = list(cleaned_texts)
            self._lexical_terms = [
                frozenset(text.split()) if text else frozenset()
                for text in lexical_texts
            ]
            self._matrix = np.stack(vectors, axis=0).astype(np.float32)

        self._cached = True

    def refresh(self) -> None:
        """Invalidate and rebuild the in-memory embedding cache."""
        with self._lock:
            self._cached = False
            self._load_cache()

    def search(
        self, query: str, limit: int = constants.SEARCH_RESULT_LIMIT
    ) -> list[SearchResult]:
        """Return the top `limit` results for a query, sorted by combined score.

        Returns an empty list when the query is empty or the DB has no poems.
        Ties in final score are broken by title ASC.
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
            query_terms = self._lexical_processor.build_query_terms(query)

            ranked: list[
                tuple[float, str, int, str, float, float]
            ] = []
            for semantic_score, title, poem_id, cleaned_text, poem_terms in zip(
                scores.tolist(),
                self._titles,
                self._ids,
                self._cleaned_texts,
                self._lexical_terms,
            ):
                lexical_score = self._lexical_score(query_terms, poem_terms)
                effective_lexical = (
                    0.0
                    if semantic_score < constants.SEMANTIC_FLOOR
                    else lexical_score
                )
                final_score = (
                    constants.SEMANTIC_WEIGHT * semantic_score
                    + constants.LEXICAL_WEIGHT * effective_lexical
                )
                ranked.append(
                    (
                        final_score,
                        title,
                        poem_id,
                        cleaned_text,
                        semantic_score,
                        effective_lexical,
                    )
                )

            ranked.sort(key=lambda row: (-row[0], row[1]))

            results: list[SearchResult] = []
            for (
                final_score,
                title,
                poem_id,
                cleaned_text,
                semantic_score,
                lexical_score,
            ) in ranked[:limit]:
                display_title = title if title else "Untitled"
                preview = _make_preview(cleaned_text)
                label = constants.label_for(final_score)
                results.append(
                    SearchResult(
                        id=poem_id,
                        title=display_title,
                        preview=preview,
                        semantic_score=float(semantic_score),
                        lexical_score=float(lexical_score),
                        final_score=float(final_score),
                        label=label,
                    )
                )

            return results

    def _lexical_score(
        self, query_terms: list[str], poem_terms: frozenset[str]
    ) -> float:
        if not query_terms:
            return 0.0

        matches = sum(
            1
            for term in query_terms
            if term in poem_terms
        )
        return (matches * constants.EXACT_LEXICAL_MATCH_VALUE) / len(query_terms)
