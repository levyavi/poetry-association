from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from poem_assoc import csv_import
from poem_assoc.db import get_connection, init_db
from poem_assoc.search import SearchService
from tests.fixtures import insert_poem_raw, make_embedding_blob


class StubEmbeddingService:
    """Return deterministic query vectors for combined-ranking tests."""

    def __init__(self, query_vectors: dict[str, list[float]]) -> None:
        first = next(iter(query_vectors.values()))
        self.dimension = len(first)
        self._query_vectors = {
            key: np.asarray(value, dtype=np.float32)
            for key, value in query_vectors.items()
        }

    def encode_query(self, query: str) -> np.ndarray:
        return self._query_vectors[query]


def _exact_fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fixture_v2_exact.csv"


def _synonym_fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fixture_v2_synonyms.csv"


def test_exact_match_scores_one_point_zero(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Lantern",
        "quiet lantern light",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="quiet lantern light",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.60]}),
        lexical_processor,
    )

    result = svc.search("quiet")[0]
    assert result.semantic_score == pytest.approx(0.60)
    assert result.lexical_score == pytest.approx(1.0)
    assert result.final_score == pytest.approx(0.68)


def test_multiword_lexical_score_is_average(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Half Match",
        "quiet lantern",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="quiet lantern",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet light": [0.50]}),
        lexical_processor,
    )

    result = svc.search("quiet light")[0]
    assert result.lexical_score == pytest.approx(0.5)
    assert result.final_score == pytest.approx(0.50)


def test_repeated_occurrences_do_not_stack(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Alpha",
        "quiet once",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="quiet once",
    )
    insert_poem_raw(
        conn,
        "Beta",
        "quiet repeated",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="quiet quiet quiet repeated",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.50, 0.50]}),
        lexical_processor,
    )

    results = svc.search("quiet")
    assert [result.title for result in results] == ["Alpha", "Beta"]
    assert results[0].lexical_score == pytest.approx(1.0)
    assert results[1].lexical_score == pytest.approx(1.0)
    assert results[0].final_score == pytest.approx(results[1].final_score)


def test_label_thresholds_use_final_score(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Threshold",
        "quiet threshold",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="quiet threshold",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.40]}),
        lexical_processor,
    )

    result = svc.search("quiet")[0]
    assert result.semantic_score == pytest.approx(0.40)
    assert result.final_score == pytest.approx(0.52)
    assert result.label == "Strong"


def test_exact_match_reorders_results_over_semantic_only_baseline(
    temp_db_path,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Lexical Winner",
        "quiet lantern",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="quiet lantern",
    )
    insert_poem_raw(
        conn,
        "Semantic Winner",
        "far river",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="far river",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.60, 0.70]}),
        lexical_processor,
    )

    results = svc.search("quiet")
    assert [result.title for result in results] == [
        "Lexical Winner",
        "Semantic Winner",
    ]
    assert results[0].final_score == pytest.approx(0.68)
    assert results[1].final_score == pytest.approx(0.56)


def test_hard_semantic_floor_blocks_lexical_boost(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Below Floor Exact",
        "quiet below floor",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="quiet below floor",
    )
    insert_poem_raw(
        conn,
        "Above Floor None",
        "distant river",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="distant river",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.19, 0.21]}),
        lexical_processor,
    )

    results = svc.search("quiet")
    assert [result.title for result in results] == [
        "Above Floor None",
        "Below Floor Exact",
    ]
    assert results[0].lexical_score == pytest.approx(0.0)
    assert results[1].lexical_score == pytest.approx(0.0)


def test_multiword_query_rewards_broader_coverage(temp_db_path, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Broader Coverage",
        "quiet light",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="quiet light",
    )
    insert_poem_raw(
        conn,
        "Narrow Coverage",
        "quiet only",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="quiet only",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet light": [0.55, 0.55]}),
        lexical_processor,
    )

    results = svc.search("quiet light")
    assert [result.title for result in results] == [
        "Broader Coverage",
        "Narrow Coverage",
    ]
    assert results[0].lexical_score == pytest.approx(1.0)
    assert results[1].lexical_score == pytest.approx(0.5)


def test_search_refresh_loads_lemmatized_search_text_from_real_sqlite(
    temp_db_path,
    lexical_processor,
):
    init_db(temp_db_path)
    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet": [0.60]}),
        lexical_processor,
    )
    assert svc.search("quiet") == []

    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Refreshed",
        "quiet lantern",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="quiet lantern",
    )
    conn.close()

    svc.refresh()
    result = svc.search("quiet")[0]
    assert result.lexical_score == pytest.approx(1.0)


def test_exact_fixture_corpus_loads_via_real_csv_path(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    csv_path = _exact_fixture_path()

    import_plan = csv_import.plan(conn, csv_path)
    result = csv_import.execute(
        conn,
        import_plan,
        embedding_service,
        lexical_processor,
    )

    count = conn.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
    lexical_rows = conn.execute(
        "SELECT lemmatized_search_text FROM poems ORDER BY id"
    ).fetchall()
    conn.close()

    assert result.imported == 3
    assert result.error is None
    assert count == 3
    assert all(row["lemmatized_search_text"] for row in lexical_rows)


def test_synonym_only_poem_receives_lexical_boost_when_semantic_floor_passes(
    temp_db_path,
    lexical_processor,
    synonym_expander,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Synonym Winner",
        "Automobile circles the room",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="automobile circle the room",
    )
    insert_poem_raw(
        conn,
        "Semantic Only",
        "River circles the room",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="river circle the room",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"car": [0.55, 0.60]}),
        lexical_processor,
        synonym_expander=synonym_expander,
    )

    results = svc.search("car")
    assert [result.title for result in results] == [
        "Synonym Winner",
        "Semantic Only",
    ]
    assert results[0].lexical_score == pytest.approx(0.7)
    assert results[0].final_score == pytest.approx(0.58)
    assert results[1].lexical_score == pytest.approx(0.0)


def test_exact_match_still_beats_synonym_match_for_same_query_word(
    temp_db_path,
    lexical_processor,
    synonym_expander,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Exact Car",
        "Car circles the room",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="car circle the room",
    )
    insert_poem_raw(
        conn,
        "Synonym Automobile",
        "Automobile circles the room",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="automobile circle the room",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"car": [0.50, 0.50]}),
        lexical_processor,
        synonym_expander=synonym_expander,
    )

    results = svc.search("car")
    assert [result.title for result in results] == [
        "Exact Car",
        "Synonym Automobile",
    ]
    assert results[0].lexical_score == pytest.approx(1.0)
    assert results[1].lexical_score == pytest.approx(0.7)


def test_disable_synonym_flag_reverts_to_exact_only_behavior(
    temp_db_path,
    lexical_processor,
    synonym_expander,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Synonym Winner",
        "Automobile circles the room",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="automobile circle the room",
    )
    insert_poem_raw(
        conn,
        "Semantic Only",
        "River circles the room",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="river circle the room",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"car": [0.55, 0.60]}),
        lexical_processor,
        synonym_expander=synonym_expander,
        enable_synonym_expansion=False,
    )

    results = svc.search("car")
    assert [result.title for result in results] == [
        "Semantic Only",
        "Synonym Winner",
    ]
    assert results[0].lexical_score == pytest.approx(0.0)
    assert results[1].lexical_score == pytest.approx(0.0)


def test_multiword_query_can_mix_exact_and_synonym_matches(
    temp_db_path,
    lexical_processor,
    synonym_expander,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Exact And Synonym",
        "Quiet automobile keeps the room",
        make_embedding_blob(2, index=0),
        lemmatized_search_text="quiet automobile keep the room",
    )
    insert_poem_raw(
        conn,
        "Exact Only",
        "Quiet lantern keeps the room",
        make_embedding_blob(2, index=1),
        lemmatized_search_text="quiet lantern keep the room",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"quiet car": [0.55, 0.55]}),
        lexical_processor,
        synonym_expander=synonym_expander,
    )

    results = svc.search("quiet car")
    assert [result.title for result in results] == [
        "Exact And Synonym",
        "Exact Only",
    ]
    assert results[0].lexical_score == pytest.approx(0.85)
    assert results[1].lexical_score == pytest.approx(0.5)


def test_synonym_search_uses_existing_lemmatized_search_text_without_schema_changes(
    temp_db_path,
    lexical_processor,
    synonym_expander,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    insert_poem_raw(
        conn,
        "Stored Lemmas",
        "This raw text does not contain the trigger word.",
        make_embedding_blob(1, index=0),
        lemmatized_search_text="automobile ash",
    )
    conn.close()

    svc = SearchService(
        temp_db_path,
        StubEmbeddingService({"car": [0.55]}),
        lexical_processor,
        synonym_expander=synonym_expander,
    )

    result = svc.search("car")[0]
    assert result.title == "Stored Lemmas"
    assert result.lexical_score == pytest.approx(0.7)


def test_synonym_fixture_corpus_loads_from_real_csv_file(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    csv_path = _synonym_fixture_path()

    import_plan = csv_import.plan(conn, csv_path)
    result = csv_import.execute(
        conn,
        import_plan,
        embedding_service,
        lexical_processor,
    )

    count = conn.execute("SELECT COUNT(*) FROM poems").fetchone()[0]
    lexical_rows = conn.execute(
        "SELECT lemmatized_search_text FROM poems ORDER BY id"
    ).fetchall()
    conn.close()

    assert result.imported == 3
    assert result.error is None
    assert count == 3
    assert all(row["lemmatized_search_text"] for row in lexical_rows)
