import io
import os

import pytest

from poem_assoc.csv_import import CsvFormatError, execute, plan
from poem_assoc.repository import create_poem, list_poems


class TestPlan:
    def test_counts_duplicates_in_db(
        self,
        db_conn,
        embedding_service,
        lexical_processor,
    ):
        """With one poem already in DB, plan reports the right counts."""
        create_poem(
            db_conn,
            "Alpha",
            "First poem text here.\nIt has two lines.",
            embedding_service,
            lexical_processor,
        )
        csv_path = os.path.join(os.path.dirname(__file__), "fixtures", "fixture_poems.csv")
        result = plan(db_conn, csv_path)
        assert result.duplicate_count == 1
        assert len(result.importable_rows) == 4

    def test_rejects_wrong_headers(self, db_conn):
        stream = io.StringIO("name,body\nfoo,bar\n")
        with pytest.raises(CsvFormatError, match="headers"):
            plan(db_conn, stream)

    def test_rejects_empty_file(self, db_conn):
        stream = io.StringIO("")
        with pytest.raises(CsvFormatError, match="empty"):
            plan(db_conn, stream)

    def test_in_file_duplicate_detection(self, db_conn):
        csv_text = "title,text\nA,same body\nA,same body\n"
        stream = io.StringIO(csv_text)
        result = plan(db_conn, stream)
        assert len(result.importable_rows) == 1
        assert result.duplicate_count == 1

    def test_same_body_different_title_not_duplicate(self, db_conn):
        csv_text = "title,text\nA,same body\nB,same body\n"
        stream = io.StringIO(csv_text)
        result = plan(db_conn, stream)
        assert len(result.importable_rows) == 2
        assert result.duplicate_count == 0

    def test_rejects_empty_title(self, db_conn):
        stream = io.StringIO("title,text\n   ,Body only\n")
        with pytest.raises(CsvFormatError, match="title is empty"):
            plan(db_conn, stream)

    def test_allows_empty_text(self, db_conn):
        stream = io.StringIO('title,text\nTitle Only,""\n')
        result = plan(db_conn, stream)
        assert len(result.importable_rows) == 1
        assert result.importable_rows[0].title == "Title Only"
        assert result.importable_rows[0].text == ""


class TestExecute:
    def test_imports_planned_rows(self, db_conn, embedding_service, lexical_processor):
        csv_text = "title,text\nOne,First unique poem\nTwo,Second unique poem\n"
        stream = io.StringIO(csv_text)
        import_plan = plan(db_conn, stream)
        result = execute(db_conn, import_plan, embedding_service, lexical_processor)
        assert result.imported == 2
        assert result.skipped_duplicates == 0
        assert list_poems(db_conn).__len__() == 2
        rows = db_conn.execute(
            "SELECT lemmatized_search_text FROM poems ORDER BY id"
        ).fetchall()
        assert all(row["lemmatized_search_text"] for row in rows)

    def test_cancellation(self, db_conn, embedding_service, lexical_processor):
        csv_text = "title,text\nA,Poem alpha\nB,Poem beta\nC,Poem gamma\nD,Poem delta\n"
        stream = io.StringIO(csv_text)
        import_plan = plan(db_conn, stream)

        call_count = 0

        def cancel_after_two():
            nonlocal call_count
            call_count += 1
            return call_count > 2

        result = execute(
            db_conn,
            import_plan,
            embedding_service,
            lexical_processor,
            cancel_flag=cancel_after_two,
        )
        assert result.imported == 2
        assert result.cancelled is True
        assert len(list_poems(db_conn)) == 2

    def test_partial_failure(self, db_conn, embedding_service, lexical_processor):
        """A forced error on the third row leaves first two rows in DB."""
        csv_text = "title,text\nA,Alpha text\nB,Beta text\nC,Gamma text\n"
        stream = io.StringIO(csv_text)
        import_plan = plan(db_conn, stream)

        original_create = __import__(
            "poem_assoc.repository", fromlist=["create_poem"]
        ).create_poem
        call_count = 0

        def failing_create(conn, title, text, es, lp):
            nonlocal call_count
            call_count += 1
            if call_count == 3:
                raise RuntimeError("Simulated failure")
            return original_create(conn, title, text, es, lp)

        import poem_assoc.csv_import as ci

        old = ci.create_poem
        ci.create_poem = failing_create
        try:
            result = execute(db_conn, import_plan, embedding_service, lexical_processor)
        finally:
            ci.create_poem = old

        assert result.imported == 2
        assert result.error is not None
        assert len(list_poems(db_conn)) == 2
        rows = db_conn.execute(
            "SELECT lemmatized_search_text FROM poems ORDER BY id"
        ).fetchall()
        assert all(row["lemmatized_search_text"] for row in rows)


class TestPerformanceSmoke:
    def test_import_10_poems_under_10s(
        self,
        db_conn,
        embedding_service,
        lexical_processor,
        tmp_path,
    ):
        """Importing 10 sample poems completes within 10 seconds."""
        import time

        csv_path = os.path.join(
            os.path.dirname(__file__), os.pardir, "sample_data", "sample_poems.csv"
        )
        start = time.monotonic()
        import_plan = plan(db_conn, csv_path)
        result = execute(db_conn, import_plan, embedding_service, lexical_processor)
        elapsed = time.monotonic() - start
        assert result.imported == 12
        assert elapsed < 10.0
