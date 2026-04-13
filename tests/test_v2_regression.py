from __future__ import annotations

import csv
from pathlib import Path

from poem_assoc import csv_import
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


def _fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fixture_v2_regression.csv"


def _load_fixture_rows() -> list[dict[str, str]]:
    with _fixture_path().open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _query_vectors() -> dict[str, list[float]]:
    return {
        "grief": [0.60, 0.55, 0.30, 0.52, 0.28, 0.19],
        "quiet": [0.58, 0.40, 0.54, 0.22, 0.21, 0.19],
        "quiet grief": [0.56, 0.55, 0.55, 0.53, 0.18, 0.19],
        "light": [0.25, 0.26, 0.24, 0.20, 0.60, 0.10],
    }


def _load_regression_corpus(
    temp_db_path: str,
    lexical_processor,
    monkeypatch,
) -> tuple[SearchService, SynonymExpander]:
    init_db(temp_db_path)
    rows = _load_fixture_rows()
    conn = get_connection(temp_db_path)
    try:
        for index, row in enumerate(rows):
            insert_poem_raw(
                conn,
                row["title"],
                row["text"],
                make_embedding_blob(len(rows), index=index),
                lemmatized_search_text=lexical_processor.build_search_text(
                    row["title"],
                    row["text"],
                ),
            )
    finally:
        conn.close()

    monkeypatch.setattr(
        lexical_processor,
        "_tag_tokens",
        lambda tokens: [
            (token, "JJ" if token == "quiet" else "NN") for token in tokens
        ],
    )
    monkeypatch.setattr(
        "poem_assoc.synonyms.wordnet.synsets",
        lambda term, pos=None: [_FakeSynset(term, "sorrow")]
        if term == "grief" and pos == "n"
        else [],
    )

    synonym_expander = SynonymExpander(lexical_processor)
    return SearchService(
        temp_db_path,
        StubEmbeddingService(_query_vectors()),
        lexical_processor,
        synonym_expander=synonym_expander,
    ), synonym_expander


def test_regression_fixture_corpus_runs_from_real_csv_file(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        import_plan = csv_import.plan(conn, _fixture_path())
        result = csv_import.execute(
            conn,
            import_plan,
            embedding_service,
            lexical_processor,
        )
        count = conn.execute("SELECT COUNT(*) AS count FROM poems").fetchone()["count"]
    finally:
        conn.close()

    assert len(import_plan.importable_rows) == 6
    assert import_plan.duplicate_count == 0
    assert result.imported == 6
    assert result.error is None
    assert count == 6


def test_v2_regression_fixture_results_are_deterministic(
    temp_db_path,
    lexical_processor,
    monkeypatch,
):
    svc, _ = _load_regression_corpus(temp_db_path, lexical_processor, monkeypatch)

    expected = {
        "grief": [
            ("Lantern Vigil", "Strong"),
            ("Ash Chorus", "Strong"),
            ("Cedar Rain", "Strong"),
            ("Harbor Stone", "Weak"),
            ("Glass Match", "Weak"),
        ],
        "quiet": [
            ("Lantern Vigil", "Strong"),
            ("Harbor Stone", "Strong"),
            ("Ash Chorus", "Strong"),
            ("Cedar Rain", "Weak"),
            ("Glass Match", "Weak"),
        ],
        "quiet grief": [
            ("Lantern Vigil", "Strong"),
            ("Ash Chorus", "Strong"),
            ("Harbor Stone", "Strong"),
            ("Cedar Rain", "Strong"),
            ("Road Static", "Weak"),
        ],
        "light": [
            ("Glass Match", "Strong"),
            ("Ash Chorus", "Weak"),
            ("Lantern Vigil", "Weak"),
            ("Harbor Stone", "Weak"),
            ("Cedar Rain", "Weak"),
        ],
    }

    for query, expected_rows in expected.items():
        first = svc.search(query)
        second = svc.search(query)
        assert len(first) == 5
        assert [(row.title, row.label) for row in first] == expected_rows
        assert [(row.title, row.label) for row in second] == expected_rows


def test_low_semantic_exact_trap_stays_below_above_floor_non_match(
    temp_db_path,
    lexical_processor,
    monkeypatch,
):
    svc, _ = _load_regression_corpus(temp_db_path, lexical_processor, monkeypatch)

    titles = [row.title for row in svc.search("quiet")]

    assert "Road Static" not in titles
    assert "Glass Match" in titles


def test_cache_hit_on_repeated_eligible_word_search_in_same_process(
    temp_db_path,
    lexical_processor,
    monkeypatch,
):
    _, expander = _load_regression_corpus(temp_db_path, lexical_processor, monkeypatch)

    first = expander.expand_term("grief", "NN")
    second = expander.expand_term("grief", "NN")

    assert first.cache_hit is False
    assert second.cache_hit is True
