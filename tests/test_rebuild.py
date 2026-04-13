import numpy as np
from pathlib import Path

from poem_assoc.constants import LEGACY_SEARCH_INDEX_VERSION, SEARCH_INDEX_VERSION
from poem_assoc.db import get_connection, init_db
from poem_assoc.index_metadata import get_index_state
from poem_assoc.rebuild import run_rebuild


def _insert_poem(
    conn,
    poem_id,
    title,
    text,
    embedding_service,
    lexical_text="",
):
    """Insert a poem with a real embedding for testing."""
    from poem_assoc.text_cleaning import clean_poem_text, compute_dedup_key

    cleaned = clean_poem_text(text)
    dedup = compute_dedup_key(cleaned)
    vector = embedding_service.encode(title, cleaned)
    blob = embedding_service.to_bytes(vector)
    with conn:
        conn.execute(
            "INSERT INTO poems "
            "(id, title, text, cleaned_text, lemmatized_search_text, embedding, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, '2024-01-01T00:00:00+00:00', '2024-01-01T00:00:00+00:00')",
            (poem_id, title, text, dedup, lexical_text, blob),
        )


def _get_embedding_bytes(conn, poem_id):
    row = conn.execute("SELECT embedding FROM poems WHERE id = ?", (poem_id,)).fetchone()
    return bytes(row["embedding"]) if row else None


def _regression_fixture_path() -> Path:
    return Path(__file__).parent / "fixtures" / "fixture_v2_regression.csv"


def test_rebuild_regenerates_all_embeddings(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        _insert_poem(conn, 1, "Rose", "A rose is a rose", embedding_service)
        _insert_poem(conn, 2, "Sky", "The sky is blue", embedding_service)
        _insert_poem(conn, 3, "Moon", "Moon over water", embedding_service)

        pre_blob = _get_embedding_bytes(conn, 1)

        result = run_rebuild(conn, embedding_service, lexical_processor)

        assert result.total == 3
        assert result.rebuilt == 3
        assert result.error is None

        post_blob = _get_embedding_bytes(conn, 1)
        assert pre_blob == post_blob

        state = get_index_state(conn)
        assert state.search_index_version == SEARCH_INDEX_VERSION
        assert state.last_successful_full_rebuild_at is not None
    finally:
        conn.close()


def test_rebuild_with_patched_service_produces_different_embeddings(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    """Use a wrapper that returns a different vector to verify rebuild actually writes."""
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        _insert_poem(conn, 1, "Rose", "A rose is a rose", embedding_service)

        pre_blob = _get_embedding_bytes(conn, 1)

        class FakeService:
            def encode(self, title, text):
                dim = embedding_service.dimension
                vec = np.ones(dim, dtype=np.float32)
                vec /= np.linalg.norm(vec)
                return vec

            def to_bytes(self, vector):
                return embedding_service.to_bytes(vector)

        result = run_rebuild(conn, FakeService(), lexical_processor)
        assert result.total == 1
        assert result.rebuilt == 1
        assert result.error is None

        post_blob = _get_embedding_bytes(conn, 1)
        assert pre_blob != post_blob
    finally:
        conn.close()


def test_rebuild_preserves_row_count_and_ids(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        for i in range(5):
            _insert_poem(conn, i + 1, f"Poem {i}", f"Text for poem {i}", embedding_service)

        pre_ids = {r["id"] for r in conn.execute("SELECT id FROM poems").fetchall()}

        result = run_rebuild(conn, embedding_service, lexical_processor)
        assert result.total == 5
        assert result.rebuilt == 5

        post_ids = {r["id"] for r in conn.execute("SELECT id FROM poems").fetchall()}
        assert pre_ids == post_ids
    finally:
        conn.close()


def test_rebuild_commits_rows_progressively(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    """Simulate a failure on the 3rd row and verify rows 1-2 already have new data."""
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        for i in range(5):
            _insert_poem(conn, i + 1, f"Poem {i}", f"Unique text {i}", embedding_service)

        call_count = 0

        class FailOnThird:
            def encode(self, title, text):
                nonlocal call_count
                call_count += 1
                if call_count == 3:
                    raise RuntimeError("injected failure")
                dim = embedding_service.dimension
                vec = np.full(dim, call_count, dtype=np.float32)
                vec /= np.linalg.norm(vec)
                return vec

            def to_bytes(self, vector):
                return embedding_service.to_bytes(vector)

        pre_blobs = {i: _get_embedding_bytes(conn, i) for i in range(1, 6)}
        with conn:
            conn.execute(
                "UPDATE app_metadata SET value = ? WHERE key = 'search_index_version'",
                (LEGACY_SEARCH_INDEX_VERSION,),
            )

        result = run_rebuild(conn, FailOnThird(), lexical_processor)
        state = get_index_state(conn)

        assert result.rebuilt == 2
        assert result.error is not None
        assert "injected failure" in result.error
        assert state.search_index_version == LEGACY_SEARCH_INDEX_VERSION

        assert _get_embedding_bytes(conn, 1) != pre_blobs[1]
        assert _get_embedding_bytes(conn, 2) != pre_blobs[2]
        assert _get_embedding_bytes(conn, 3) == pre_blobs[3]
        assert _get_embedding_bytes(conn, 4) == pre_blobs[4]
        assert _get_embedding_bytes(conn, 5) == pre_blobs[5]

        rows = conn.execute(
            "SELECT id, lemmatized_search_text FROM poems ORDER BY id"
        ).fetchall()
        assert rows[0]["lemmatized_search_text"]
        assert rows[1]["lemmatized_search_text"]
        assert rows[2]["lemmatized_search_text"] == ""
    finally:
        conn.close()


def test_rebuild_zero_poems(temp_db_path, embedding_service, lexical_processor):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        result = run_rebuild(conn, embedding_service, lexical_processor)
        assert result.total == 0
        assert result.rebuilt == 0
        assert result.error is None
    finally:
        conn.close()


def test_manual_rebuild_backfills_lexical_field_for_existing_rows(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        _insert_poem(
            conn,
            1,
            "Running Dogs",
            "Leaves were falling",
            embedding_service,
            lexical_text="",
        )
        with conn:
            conn.execute(
                "UPDATE app_metadata SET value = ? WHERE key = 'search_index_version'",
                (LEGACY_SEARCH_INDEX_VERSION,),
            )

        result = run_rebuild(conn, embedding_service, lexical_processor)
        row = conn.execute(
            "SELECT lemmatized_search_text FROM poems WHERE id = 1"
        ).fetchone()
        state = get_index_state(conn)

        assert result.error is None
        assert row["lemmatized_search_text"] == "run dog leaf be fall"
        assert state.search_index_version == SEARCH_INDEX_VERSION
    finally:
        conn.close()


def test_rebuild_regenerates_lexical_text_for_regression_fixture(
    temp_db_path,
    embedding_service,
    lexical_processor,
):
    init_db(temp_db_path)
    conn = get_connection(temp_db_path)
    try:
        import csv

        with _regression_fixture_path().open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for poem_id, row in enumerate(reader, start=1):
                _insert_poem(
                    conn,
                    poem_id,
                    row["title"],
                    row["text"],
                    embedding_service,
                    lexical_text="",
                )

        with conn:
            conn.execute(
                "UPDATE app_metadata SET value = ? WHERE key = 'search_index_version'",
                (LEGACY_SEARCH_INDEX_VERSION,),
            )

        result = run_rebuild(conn, embedding_service, lexical_processor)
        rows = conn.execute(
            "SELECT title, lemmatized_search_text FROM poems ORDER BY id"
        ).fetchall()
        state = get_index_state(conn)

        assert result.error is None
        assert result.rebuilt == 6
        assert state.search_index_version == SEARCH_INDEX_VERSION
        assert all(row["lemmatized_search_text"] for row in rows)
        assert rows[0]["title"] == "Lantern Vigil"
        assert rows[0]["lemmatized_search_text"] == (
            "lantern vigil quiet grief lantern by the river"
        )
    finally:
        conn.close()
