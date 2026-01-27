"""Tests for text-to-markdown conversion."""

import pytest
from regkb.extraction import TextExtractor


@pytest.fixture
def extractor(tmp_path):
    """Create a TextExtractor instance with a temp output dir (bypasses config singleton)."""
    return TextExtractor(output_dir=tmp_path)


class TestConvertToMarkdown:
    def test_adds_title_header(self, extractor):
        result = extractor._convert_to_markdown("Some text", "My Document")
        assert result.startswith("# My Document\n")

    def test_preserves_paragraphs(self, extractor):
        text = "First paragraph\n\nSecond paragraph"
        result = extractor._convert_to_markdown(text, "Title")
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_collapses_blank_lines(self, extractor):
        text = "Line one\n\n\n\n\nLine two"
        result = extractor._convert_to_markdown(text, "Title")
        assert "\n\n\n" not in result


class TestIsPotentialHeading:
    def test_all_caps_line(self, extractor):
        assert extractor._is_potential_heading("INTRODUCTION") is True

    def test_numbered_section_header(self, extractor):
        assert extractor._is_potential_heading("1.2 Scope") is True

    def test_rejects_long_lines(self, extractor):
        long_line = "THIS IS A VERY LONG LINE THAT EXCEEDS " * 5
        assert extractor._is_potential_heading(long_line) is False

    def test_rejects_short_lines(self, extractor):
        assert extractor._is_potential_heading("AB") is False


class TestIsListItem:
    def test_bullet_chars(self, extractor):
        assert extractor._is_list_item("\u2022 Item") is True

    def test_dash_bullet(self, extractor):
        assert extractor._is_list_item("- Item") is True

    def test_asterisk_bullet(self, extractor):
        assert extractor._is_list_item("* Item") is True

    def test_numbered_list(self, extractor):
        assert extractor._is_list_item("1. Item") is True

    def test_lettered_list(self, extractor):
        assert extractor._is_list_item("a) Item") is True

    def test_parenthetical_list(self, extractor):
        assert extractor._is_list_item("(b) Item") is True


class TestFormatListItem:
    def test_bullet_to_dash(self, extractor):
        result = extractor._format_list_item("\u2022 Item text")
        assert result.startswith("- ")

    def test_normalizes_numbered(self, extractor):
        result = extractor._format_list_item("1) Item text")
        assert result.startswith("1. ")
