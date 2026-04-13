from __future__ import annotations

import logging

import pytest

from poem_assoc.db import get_connection, init_db
from poem_assoc.search import SearchService
from poem_assoc.synonyms import SynonymExpander
from tests.fixtures import insert_poem_raw, make_embedding_blob


class StubEmbeddingService:
    def __init__(self, query_vectors: dict[str, list[float]]) -> None:
        first = next(iter(query_vectors.values()))
        self.dimension = len(first)
        self._query_vectors = query_vectors

    def encode_query(self, query: str):
        return self._query_vectors[query]


class _FakeLemma:
    def __init__(self, name: str) -> None:
        self._name = name

    def name(self) -> str:
        return self._name


class _FakeSynset:
    def __init__(self, *lemma_names: str) -> None:
        self._lemmas = [_FakeLemma(name) for name in lemma_names]

    def lemmas(self) -> list[_FakeLemma]:
        return list(self._lemmas)


class _ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


class _ExplodingHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        raise RuntimeError("handler boom")


def _make_logger(name: str) -> tuple[logging.Logger, _ListHandler]:
    logger = logging.Logger(name, level=logging.INFO)
    logger.propagate = False
    handler = _ListHandler()
    logger.addHandler(handler)
    return logger, handler


def test_search_logs_required_diagnostics_fields(
    temp_db_path,
    lexical_processor,
    monkeypatch,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Lantern Vigil",
        "quiet grief lantern by the river",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="lantern vigil quiet grief lantern by the river",
    )
    insert_poem_raw(
        conn,
        "Ash Chorus",
        "quiet sorrow lantern by the river",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="ash chorus quiet sorrow lantern by the river",
    )
    conn.close()

    monkeypatch.setattr(
        lexical_processor,
        "_tag_tokens",
        lambda tokens: [(token, "NN") for token in tokens],
    )
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [_FakeSynset(term, "sorrow")]
        if term == "grief" and pos == "n"
        else [],
    )

    logger, handler = _make_logger("test.search.diagnostics.fields")
    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"grief": [0.60, 0.55]}),
        lexical_processor,
        synonym_expander=SynonymExpander(lexical_processor),
        logger=logger,
    )

    results = svc.search("grief")

    assert [result.title for result in results] == ["Lantern Vigil", "Ash Chorus"]
    assert len(handler.records) == 1
    record = handler.records[0]
    payload = record.diagnostics

    assert payload["original_query"] == "grief"
    assert payload["normalized_semantic_query"] == "grief"
    assert payload["lexical_query_words"] == ["grief"]
    assert payload["pos_tags"] == {"grief": "NN"}
    assert payload["synonym_expansions"] == {"grief": ["sorrow"]}
    assert payload["synonym_cache"] == {"grief": "miss"}
    assert payload["results"][0]["semantic_score"] == pytest.approx(0.6)
    assert payload["results"][0]["lexical_score"] == pytest.approx(1.0)
    assert payload["results"][0]["final_score"] == pytest.approx(0.68)
    assert payload["results"][0]["match_reasons"]["grief"]["match_type"] == "exact"
    assert payload["results"][1]["match_reasons"]["grief"]["match_type"] == "synonym"
    assert (
        payload["results"][1]["match_reasons"]["grief"]["triggering_synonym"]
        == "sorrow"
    )
    assert "text" not in payload["results"][0]
    assert "quiet grief lantern by the river" not in record.getMessage()
    assert "quiet sorrow lantern by the river" not in record.getMessage()


def test_cache_hit_is_logged_on_repeated_query(
    temp_db_path,
    lexical_processor,
    monkeypatch,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Lantern Vigil",
        "quiet grief lantern by the river",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="lantern vigil quiet grief lantern by the river",
    )
    conn.close()

    call_count = 0

    def fake_synsets(term: str, pos: str | None = None):
        nonlocal call_count
        call_count += 1
        return [_FakeSynset(term, "sorrow")]

    monkeypatch.setattr(
        lexical_processor,
        "_tag_tokens",
        lambda tokens: [(token, "NN") for token in tokens],
    )
    monkeypatch.setattr("poem_assoc.synonyms.wordnet.synsets", fake_synsets)

    logger, handler = _make_logger("test.search.diagnostics.cache")
    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"grief": [0.60]}),
        lexical_processor,
        synonym_expander=SynonymExpander(lexical_processor),
        logger=logger,
    )

    svc.search("grief")
    svc.search("grief")

    assert len(handler.records) == 2
    assert handler.records[0].diagnostics["synonym_cache"] == {"grief": "miss"}
    assert handler.records[1].diagnostics["synonym_cache"] == {"grief": "hit"}
    assert call_count == 1


def test_logging_failures_do_not_break_search(
    temp_db_path,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Lantern Vigil",
        "quiet grief lantern by the river",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="lantern vigil quiet grief lantern by the river",
    )
    conn.close()

    logger = logging.Logger("test.search.diagnostics.failure", level=logging.INFO)
    logger.propagate = False
    logger.addHandler(_ExplodingHandler())

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"grief": [0.60]}),
        lexical_processor,
        logger=logger,
    )

    results = svc.search("grief")

    assert [result.title for result in results] == ["Lantern Vigil"]
