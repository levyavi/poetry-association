"""Tests for SearchService, SearchResult, constants, and iter_embeddings."""

from __future__ import annotations

import time

import numpy as np
import pytest

from poem_assoc.constants import label_for
from poem_assoc.db import get_connection, init_db
from poem_assoc.repository import create_poem, iter_embeddings
from poem_assoc.search import SearchService, _make_preview
from tests.fixtures import insert_poem_raw, make_embedding_blob


def test_label_for_strong():
    assert label_for(0.50) == "Strong"


def test_label_for_at_strong_threshold():
    assert label_for(0.45) == "Strong"


def test_label_for_moderate_lower_bound():
    assert label_for(0.30) == "Moderate"


def test_label_for_moderate_upper_bound():
    assert label_for(0.449999) == "Moderate"


def test_label_for_weak():
    assert label_for(0.20) == "Weak"


def test_label_for_below_zero():
    assert label_for(-0.10) == "Weak"


def test_preview_single_line():
    assert _make_preview("only one line") == "only one line"


def test_preview_two_lines_no_ellipsis():
    text = "line one\nline two"
    assert _make_preview(text) == "line one\nline two"
    assert "\u2026" not in _make_preview(text)


def test_preview_truncates_to_two_lines():
    text = "line one\nline two\nline three\nline four"
    preview = _make_preview(text)
    assert preview.endswith("\u2026")
    assert "line one" in preview
    assert "line two" in preview
    assert "line three" not in preview


def test_preview_skips_blank_lines():
    text = "\n\nfirst real line\n\nsecond real line\nthird real line"
    preview = _make_preview(text)
    assert "first real line" in preview
    assert "second real line" in preview
    assert preview.endswith("\u2026")


def test_untitled_rendered_when_title_blank(temp_db_path, embedding_service):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    blob = make_embedding_blob(embedding_service.dimension)
    insert_poem_raw(conn, "", "some poem text here about grief", blob)
    conn.close()

    svc = SearchService(temp_db_path, embedding_service)
    results = svc.search("poem")
    assert len(results) == 1
    assert results[0].title == "Untitled"


@pytest.fixture()
def search_db(temp_db_path):
    init_db(temp_db_path)
    return temp_db_path


@pytest.fixture()
def search_svc(search_db, embedding_service):
    return SearchService(search_db, embedding_service)


def test_search_empty_query_returns_empty_list(search_svc):
    assert search_svc.search("") == []


def test_search_whitespace_only_returns_empty_list(search_svc):
    assert search_svc.search("   ") == []


def test_search_empty_db_returns_empty_list(search_svc):
    assert search_svc.search("grief") == []


def test_search_fewer_than_five_poems(search_db, embedding_service, lexical_processor):
    conn = get_connection(search_db)
    for i in range(3):
        create_poem(
            conn,
            f"Poem {i}",
            f"This is the text for poem number {i} about autumn leaves",
            embedding_service,
            lexical_processor,
        )
    conn.close()

    svc = SearchService(search_db, embedding_service)
    results = svc.search("autumn poem")
    assert len(results) == 3


def test_search_returns_top_5(search_db, embedding_service, lexical_processor):
    conn = get_connection(search_db)
    for i in range(8):
        create_poem(
            conn,
            f"Poem {i}",
            f"This is poem {i} about nature seasons and the passing of time",
            embedding_service,
            lexical_processor,
        )
    conn.close()

    svc = SearchService(search_db, embedding_service)
    results = svc.search("nature seasons")
    assert len(results) == 5


def test_search_sort_ties_broken_by_title(search_db, embedding_service):
    dim = embedding_service.dimension
    blob = make_embedding_blob(dim, index=0)

    conn = get_connection(search_db)
    for title in ["Zebra", "Apple", "Mango"]:
        insert_poem_raw(conn, title, f"poem text about {title.lower()}", blob)
    conn.close()

    svc = SearchService(search_db, embedding_service)
    results = svc.search("anything")
    assert [r.title for r in results] == ["Apple", "Mango", "Zebra"]


def test_search_result_has_label(search_db, embedding_service, lexical_processor):
    conn = get_connection(search_db)
    create_poem(
        conn,
        "Leaf Fall",
        "leaves falling in autumn wind",
        embedding_service,
        lexical_processor,
    )
    conn.close()

    svc = SearchService(search_db, embedding_service)
    results = svc.search("autumn")
    assert results[0].label in ("Strong", "Moderate", "Weak")


def test_search_refresh_picks_up_new_poem(search_db, embedding_service, lexical_processor):
    svc = SearchService(search_db, embedding_service)
    assert svc.search("nature") == []

    conn = get_connection(search_db)
    create_poem(
        conn,
        "Nature Poem",
        "trees and rivers in the forest",
        embedding_service,
        lexical_processor,
    )
    conn.close()

    svc.refresh()
    results = svc.search("forest trees")
    assert len(results) == 1


def test_iter_embeddings_matches_inserted_rows(
    db_conn,
    embedding_service,
    lexical_processor,
):
    for i in range(3):
        create_poem(
            db_conn,
            f"Poem {i}",
            f"poem text number {i}",
            embedding_service,
            lexical_processor,
        )

    rows = list(iter_embeddings(db_conn))
    assert len(rows) == 3
    for poem_id, title, cleaned_text, vec in rows:
        assert isinstance(poem_id, int)
        assert isinstance(title, str)
        assert vec.shape == (embedding_service.dimension,)
        assert vec.dtype == np.float32


def test_iter_embeddings_empty_db(db_conn):
    assert list(iter_embeddings(db_conn)) == []


def test_search_latency_under_1s(search_db, embedding_service):
    dim = embedding_service.dimension
    conn = get_connection(search_db)
    for i in range(50):
        blob = make_embedding_blob(dim, index=i)
        insert_poem_raw(conn, f"Poem {i}", f"poem about nature and season {i}", blob)
    conn.close()

    svc = SearchService(search_db, embedding_service)
    svc.refresh()

    start = time.monotonic()
    svc.search("nature seasons")
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, f"search took {elapsed:.3f}s, expected < 1s"
