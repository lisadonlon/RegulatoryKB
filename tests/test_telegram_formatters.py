"""Tests for Telegram message formatters."""

from regkb.telegram.formatters import (
    bold,
    code,
    escape_md,
    format_search_result,
    format_search_results,
    format_stats,
    italic,
    link,
)


class TestEscapeMd:
    def test_empty_string(self):
        assert escape_md("") == ""

    def test_no_special_chars(self):
        assert escape_md("hello world") == "hello world"

    def test_escapes_dots(self):
        assert escape_md("v1.0.0") == "v1\\.0\\.0"

    def test_escapes_parentheses(self):
        assert escape_md("510(k)") == "510\\(k\\)"

    def test_escapes_brackets(self):
        assert escape_md("[test]") == "\\[test\\]"

    def test_escapes_hash(self):
        assert escape_md("#1 item") == "\\#1 item"

    def test_escapes_pipe(self):
        assert escape_md("a | b") == "a \\| b"

    def test_escapes_dash(self):
        assert escape_md("ISO-13485") == "ISO\\-13485"


class TestFormatHelpers:
    def test_bold(self):
        assert bold("hello") == "*hello*"

    def test_bold_escapes(self):
        assert bold("v1.0") == "*v1\\.0*"

    def test_italic(self):
        assert italic("hello") == "_hello_"

    def test_code(self):
        assert code("hello") == "`hello`"

    def test_link(self):
        result = link("Click here", "https://example.com")
        assert "[Click here]" in result
        assert "(https://example.com)" in result

    def test_link_escapes_parens_in_url(self):
        result = link("FDA", "https://fda.gov/510(k)")
        assert "%28" in result
        assert "%29" in result


class TestFormatStats:
    def test_basic_stats(self):
        stats = {"total_documents": 130, "by_type": {"guidance": 50}, "by_jurisdiction": {"EU": 30}}
        result = format_stats(stats, pending_count=5)
        assert "130" in result
        assert "guidance" in result
        assert "Pending" in result

    def test_zero_pending(self):
        stats = {"total_documents": 0}
        result = format_stats(stats, pending_count=0)
        assert "Pending" not in result


class TestFormatSearchResult:
    def test_basic_result(self):
        result = format_search_result(
            {
                "title": "MDR 2017/745",
                "jurisdiction": "EU",
                "document_type": "regulation",
                "score": 0.95,
            },
            index=0,
        )
        assert "MDR" in result
        assert "EU" in result

    def test_with_excerpt(self):
        result = format_search_result(
            {"title": "Test Doc", "excerpt": "Some relevant text here"},
            index=1,
        )
        assert "relevant text" in result


class TestFormatSearchResults:
    def test_no_results(self):
        result = format_search_results([], "test query")
        assert "No results" in result

    def test_with_results(self):
        results = [
            {"title": "Doc 1", "jurisdiction": "EU"},
            {"title": "Doc 2", "jurisdiction": "FDA"},
        ]
        result = format_search_results(results, "medical device")
        assert "medical device" in result
        assert "2 result" in result
