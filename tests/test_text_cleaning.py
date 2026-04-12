import pytest

from poem_assoc.text_cleaning import clean_poem_text, clean_query, compute_dedup_key


class TestCleanPoemText:
    def test_preserves_case(self):
        assert clean_poem_text("Hello World") == "Hello World"

    def test_normalizes_line_endings(self):
        assert clean_poem_text("line1\r\nline2\rline3") == "line1\nline2\nline3"

    def test_collapses_blank_lines(self):
        text = "line1\n\n\n\n\nline2"
        result = clean_poem_text(text)
        assert result == "line1\n\n\nline2"

    def test_trims_trailing_space_per_line(self):
        result = clean_poem_text("hello   \nworld  ")
        assert result == "hello\nworld"

    def test_strips_leading_trailing_whitespace(self):
        assert clean_poem_text("  hello  ") == "hello"

    def test_preserves_internal_line_breaks(self):
        text = "line1\nline2\nline3"
        assert clean_poem_text(text) == text

    def test_raises_on_none(self):
        with pytest.raises(ValueError):
            clean_poem_text(None)


class TestComputeDedupKey:
    def test_is_case_sensitive(self):
        assert compute_dedup_key("Hello") != compute_dedup_key("hello")

    def test_normalizes_whitespace(self):
        a = compute_dedup_key("hello   world\n  foo")
        b = compute_dedup_key("hello world foo")
        assert a == b

    def test_same_poem_different_indentation(self):
        a = compute_dedup_key("  The sun rises\n    over the hill")
        b = compute_dedup_key("The sun rises\nover the hill")
        assert a == b


class TestCleanQuery:
    def test_lowercases_and_trims(self):
        assert clean_query("  Quiet GRIEF  ") == "quiet grief"

    def test_empty_or_whitespace_returns_empty(self):
        assert clean_query("") == ""
        assert clean_query("   ") == ""

    def test_normalizes_smart_quotes(self):
        assert clean_query("\u201chello\u201d") == '"hello"'

    def test_collapses_internal_whitespace(self):
        assert clean_query("one   two   three") == "one two three"
