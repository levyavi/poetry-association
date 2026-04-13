from __future__ import annotations

import json
import logging
import threading
from dataclasses import dataclass

import numpy as np

from . import constants
from . import repository
from .db import get_connection
from .embedding import EmbeddingService
from .lexical import LexicalTextProcessor, TaggedQueryTerm
from .synonyms import SynonymExpander, SynonymExpansion
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
        synonym_expander: SynonymExpander | None = None,
        *,
        enable_synonym_expansion: bool = True,
        logger: logging.Logger | None = None,
    ) -> None:
        self._db_path = db_path
        self._embedding_service = embedding_service
        self._lexical_processor = lexical_processor
        self._synonym_expander = synonym_expander
        self._enable_synonym_expansion = enable_synonym_expansion
        self._logger = logger or logging.getLogger("poem_assoc.search")
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
            tagged_query_terms = self._lexical_processor.build_tagged_query_terms(query)
            synonym_map = self._build_synonym_map(tagged_query_terms)

            ranked: list[
                tuple[float, str, int, str, float, float, float, dict[str, dict[str, str | None]]]
            ] = []
            for semantic_score, title, poem_id, cleaned_text, poem_terms in zip(
                scores.tolist(),
                self._titles,
                self._ids,
                self._cleaned_texts,
                self._lexical_terms,
            ):
                raw_lexical_score, match_reasons = self._lexical_score(
                    tagged_query_terms,
                    poem_terms,
                    synonym_map,
                )
                effective_lexical = (
                    0.0
                    if semantic_score < constants.SEMANTIC_FLOOR
                    else raw_lexical_score
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
                        raw_lexical_score,
                        match_reasons,
                    )
                )

            ranked.sort(key=lambda row: (-row[0], row[1]))

            results: list[SearchResult] = []
            diagnostic_results: list[dict[str, object]] = []
            for (
                final_score,
                title,
                poem_id,
                cleaned_text,
                semantic_score,
                lexical_score,
                raw_lexical_score,
                match_reasons,
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
                diagnostic_results.append(
                    {
                        "poem_id": poem_id,
                        "title": display_title,
                        "semantic_score": float(semantic_score),
                        "lexical_score": float(lexical_score),
                        "raw_lexical_score": float(raw_lexical_score),
                        "final_score": float(final_score),
                        "label": label,
                        "match_reasons": match_reasons,
                    }
                )

            self._log_diagnostics(
                {
                    "original_query": query,
                    "normalized_semantic_query": cleaned,
                    "lexical_query_words": [
                        tagged_term.term for tagged_term in tagged_query_terms
                    ],
                    "pos_tags": {
                        tagged_term.term: tagged_term.pos_tag
                        for tagged_term in tagged_query_terms
                    },
                    "synonym_expansions": {
                        term: list(expansion.synonyms)
                        for term, expansion in synonym_map.items()
                        if expansion.synonyms
                    },
                    "synonym_cache": {
                        term: ("hit" if expansion.cache_hit else "miss")
                        for term, expansion in synonym_map.items()
                        if expansion.cache_hit is not None
                    },
                    "results": diagnostic_results,
                }
            )

            return results

    def _lexical_score(
        self,
        tagged_query_terms: list[TaggedQueryTerm],
        poem_terms: frozenset[str],
        synonym_map: dict[str, SynonymExpansion],
    ) -> tuple[float, dict[str, dict[str, str | None]]]:
        if not tagged_query_terms:
            return 0.0, {}

        total = 0.0
        match_reasons: dict[str, dict[str, str | None]] = {}
        for tagged_term in tagged_query_terms:
            match_reason = {"match_type": "none", "triggering_synonym": None}
            if tagged_term.term in poem_terms:
                total += constants.EXACT_LEXICAL_MATCH_VALUE
                match_reason["match_type"] = "exact"
                match_reasons[tagged_term.term] = match_reason
                continue

            expansion = synonym_map.get(tagged_term.term)
            matched_synonym = None
            if expansion is not None:
                matched_synonym = next(
                    (
                        synonym
                        for synonym in expansion.synonyms
                        if synonym in poem_terms
                    ),
                    None,
                )
            if matched_synonym is not None:
                total += constants.SYNONYM_LEXICAL_MATCH_VALUE
                match_reason["match_type"] = "synonym"
                match_reason["triggering_synonym"] = matched_synonym
            match_reasons[tagged_term.term] = match_reason

        return total / len(tagged_query_terms), match_reasons

    def _build_synonym_map(
        self,
        tagged_query_terms: list[TaggedQueryTerm],
    ) -> dict[str, SynonymExpansion]:
        if not self._enable_synonym_expansion or self._synonym_expander is None:
            return {}

        return self._synonym_expander.expand_terms(tagged_query_terms)

    def _log_diagnostics(self, payload: dict[str, object]) -> None:
        if not self._logger.isEnabledFor(logging.INFO):
            return

        try:
            self._logger.info(
                "search_diagnostics %s",
                json.dumps(payload, sort_keys=True, separators=(",", ":")),
                extra={"diagnostics": payload},
            )
        except Exception:
            return
