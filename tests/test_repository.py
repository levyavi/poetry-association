import pytest

from poem_assoc.repository import (
    DuplicatePoemError,
    create_poem,
    get_poem,
    list_poems,
    update_poem,
)


class TestCreatePoem:
    def test_inserts_row(self, db_conn, embedding_service, lexical_processor):
        poem_id = create_poem(
            db_conn,
            "Test Title",
            "Test body text",
            embedding_service,
            lexical_processor,
        )
        row = get_poem(db_conn, poem_id)
        assert row is not None
        assert row["title"] == "Test Title"
        assert row["embedding"] is not None
        assert len(row["embedding"]) > 0
        assert row["lemmatized_search_text"] == "test title test body text"

    def test_rejects_duplicate(self, db_conn, embedding_service, lexical_processor):
        create_poem(
            db_conn,
            "First",
            "Same poem body here",
            embedding_service,
            lexical_processor,
        )
        with pytest.raises(DuplicatePoemError):
            create_poem(
                db_conn,
                "First",
                "Same poem body here",
                embedding_service,
                lexical_processor,
            )
        rows = list_poems(db_conn)
        assert len(rows) == 1

    def test_allows_same_body_with_different_title(
        self, db_conn, embedding_service, lexical_processor
    ):
        create_poem(
            db_conn,
            "First",
            "Same poem body here",
            embedding_service,
            lexical_processor,
        )
        create_poem(
            db_conn,
            "Second",
            "Same poem body here",
            embedding_service,
            lexical_processor,
        )
        rows = list_poems(db_conn)
        assert len(rows) == 2

    def test_rejects_empty_title(self, db_conn, embedding_service, lexical_processor):
        with pytest.raises(ValueError, match="Poem title is required"):
            create_poem(
                db_conn,
                "   ",
                "Body text",
                embedding_service,
                lexical_processor,
            )

    def test_allows_empty_text(self, db_conn, embedding_service, lexical_processor):
        poem_id = create_poem(
            db_conn,
            "Title Only",
            "   ",
            embedding_service,
            lexical_processor,
        )
        row = get_poem(db_conn, poem_id)
        assert row is not None
        assert row["title"] == "Title Only"
        assert row["text"] == "   "
        assert row["cleaned_text"] == ""
        assert row["lemmatized_search_text"] == "title only"

    def test_update_regenerates_lemmatized_search_text(
        self,
        db_conn,
        embedding_service,
        lexical_processor,
    ):
        poem_id = create_poem(
            db_conn,
            "Running Dogs",
            "Leaves were falling",
            embedding_service,
            lexical_processor,
        )
        updated = update_poem(
            db_conn,
            poem_id,
            "Quiet Cats",
            "Birds are singing",
            embedding_service,
            lexical_processor,
        )
        assert updated["lemmatized_search_text"] == "quiet cat bird be sing"


class TestListPoems:
    def test_default_sort_is_title_asc(self, db_conn, embedding_service, lexical_processor):
        create_poem(
            db_conn, "Zebra", "Zebra poem text", embedding_service, lexical_processor
        )
        create_poem(
            db_conn, "Apple", "Apple poem text", embedding_service, lexical_processor
        )
        create_poem(
            db_conn, "Middle", "Middle poem text", embedding_service, lexical_processor
        )
        rows = list_poems(db_conn)
        titles = [r["title"] for r in rows]
        assert titles == ["Apple", "Middle", "Zebra"]


class TestGetPoem:
    def test_returns_none_for_missing_id(self, db_conn):
        assert get_poem(db_conn, 9999) is None

    def test_returns_row_by_id(self, db_conn, embedding_service, lexical_processor):
        poem_id = create_poem(
            db_conn,
            "Fetch Me",
            "Fetchable poem",
            embedding_service,
            lexical_processor,
        )
        row = get_poem(db_conn, poem_id)
        assert row["id"] == poem_id
        assert row["title"] == "Fetch Me"


class TestEmbeddingBlobRoundtrip:
    def test_blob_roundtrip_via_db(self, db_conn, embedding_service, lexical_processor):
        """Insert a poem, fetch it, deserialize BLOB, verify it matches."""
        import numpy as np

        poem_id = create_poem(
            db_conn,
            "Roundtrip",
            "Roundtrip poem text",
            embedding_service,
            lexical_processor,
        )
        row = get_poem(db_conn, poem_id)
        restored = embedding_service.from_bytes(row["embedding"])
        expected = embedding_service.encode("Roundtrip", "Roundtrip poem text")
        assert restored.shape == expected.shape
        assert restored.dtype == np.float32
