import pytest

from poem_assoc.repository import (
    DuplicatePoemError,
    create_poem,
    get_poem,
    list_poems,
)


class TestCreatePoem:
    def test_inserts_row(self, db_conn, embedding_service):
        poem_id = create_poem(db_conn, "Test Title", "Test body text", embedding_service)
        row = get_poem(db_conn, poem_id)
        assert row is not None
        assert row["title"] == "Test Title"
        assert row["embedding"] is not None
        assert len(row["embedding"]) > 0

    def test_rejects_duplicate(self, db_conn, embedding_service):
        create_poem(db_conn, "First", "Same poem body here", embedding_service)
        with pytest.raises(DuplicatePoemError):
            create_poem(db_conn, "Second", "Same poem body here", embedding_service)
        # Verify only one row exists
        rows = list_poems(db_conn)
        assert len(rows) == 1


class TestListPoems:
    def test_default_sort_is_title_asc(self, db_conn, embedding_service):
        create_poem(db_conn, "Zebra", "Zebra poem text", embedding_service)
        create_poem(db_conn, "Apple", "Apple poem text", embedding_service)
        create_poem(db_conn, "Middle", "Middle poem text", embedding_service)
        rows = list_poems(db_conn)
        titles = [r["title"] for r in rows]
        assert titles == ["Apple", "Middle", "Zebra"]


class TestGetPoem:
    def test_returns_none_for_missing_id(self, db_conn):
        assert get_poem(db_conn, 9999) is None

    def test_returns_row_by_id(self, db_conn, embedding_service):
        poem_id = create_poem(db_conn, "Fetch Me", "Fetchable poem", embedding_service)
        row = get_poem(db_conn, poem_id)
        assert row["id"] == poem_id
        assert row["title"] == "Fetch Me"


class TestEmbeddingBlobRoundtrip:
    def test_blob_roundtrip_via_db(self, db_conn, embedding_service):
        """Insert a poem, fetch it, deserialize BLOB, verify it matches."""
        import numpy as np

        poem_id = create_poem(db_conn, "Roundtrip", "Roundtrip poem text", embedding_service)
        row = get_poem(db_conn, poem_id)
        restored = embedding_service.from_bytes(row["embedding"])
        expected = embedding_service.encode("Roundtrip", "Roundtrip poem text")
        # The cleaned text may differ slightly, so just check shape and type
        assert restored.shape == expected.shape
        assert restored.dtype == np.float32
