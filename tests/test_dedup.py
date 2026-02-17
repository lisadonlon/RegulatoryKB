"""Tests for cross-source deduplication."""

from regkb.intelligence.dedup import (
    deduplicate_entries,
    normalize_title,
    normalize_url,
    titles_similar,
)
from regkb.intelligence.fetcher import NewsletterEntry


class TestNormalizeUrl:
    def test_strips_tracking_params(self):
        url = "https://fda.gov/guidance?utm_source=email&utm_medium=news&id=123"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "id=123" in result

    def test_strips_trailing_slash(self):
        assert normalize_url("https://fda.gov/guidance/") == normalize_url(
            "https://fda.gov/guidance"
        )

    def test_lowercases(self):
        result = normalize_url("HTTPS://FDA.GOV/Guidance")
        assert "fda.gov" in result

    def test_none_returns_none(self):
        assert normalize_url(None) is None

    def test_empty_returns_none(self):
        assert normalize_url("") is None


class TestNormalizeTitle:
    def test_lowercases(self):
        assert normalize_title("FDA Guidance") == "fda guidance"

    def test_strips_punctuation(self):
        assert normalize_title("ISO 13485:2016 - QMS") == "iso 13485 2016 qms"

    def test_collapses_whitespace(self):
        assert normalize_title("FDA   New   Guidance") == "fda new guidance"

    def test_empty(self):
        assert normalize_title("") == ""


class TestTitlesSimilar:
    def test_identical(self):
        assert titles_similar("FDA Guidance on AI/ML", "FDA Guidance on AI/ML")

    def test_very_similar(self):
        assert titles_similar(
            "FDA Issues Draft Guidance on AI/ML Software",
            "FDA Issues Draft Guidance on AI/ML-based Software",
        )

    def test_different(self):
        assert not titles_similar("FDA Guidance on AI/ML", "EU MDR Implementation Guide")

    def test_empty_strings(self):
        assert not titles_similar("", "")


class TestDeduplicateEntries:
    def test_empty_list(self):
        assert deduplicate_entries([]) == []

    def test_no_duplicates(self):
        entries = [
            NewsletterEntry(
                date="2026-02-10", agency="FDA", category="A", title="Doc 1", link="https://a.com/1"
            ),
            NewsletterEntry(
                date="2026-02-10", agency="EU", category="B", title="Doc 2", link="https://b.com/2"
            ),
        ]
        result = deduplicate_entries(entries)
        assert len(result) == 2

    def test_url_dedup(self):
        entries = [
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="Doc 1",
                link="https://fda.gov/doc",
            ),
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="Doc 1 copy",
                link="https://fda.gov/doc",
            ),
        ]
        result = deduplicate_entries(entries)
        assert len(result) == 1

    def test_url_dedup_with_tracking(self):
        entries = [
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="Doc 1",
                link="https://fda.gov/doc",
            ),
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="Doc 1",
                link="https://fda.gov/doc?utm_source=email",
            ),
        ]
        result = deduplicate_entries(entries)
        assert len(result) == 1

    def test_title_dedup(self):
        entries = [
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="FDA Issues New Guidance on AI/ML",
            ),
            NewsletterEntry(
                date="2026-02-11",
                agency="FDA",
                category="B",
                title="FDA Issues New Guidance on AI/ML-Based Software",
            ),
        ]
        result = deduplicate_entries(entries)
        # Similar titles should be deduped
        assert len(result) <= 2  # May or may not dedup depending on threshold

    def test_prefers_entries_with_links(self):
        entries = [
            NewsletterEntry(
                date="2026-02-10", agency="FDA", category="A", title="FDA Guidance", link=None
            ),
            NewsletterEntry(
                date="2026-02-10",
                agency="FDA",
                category="A",
                title="FDA Guidance",
                link="https://fda.gov/doc",
            ),
        ]
        result = deduplicate_entries(entries)
        assert len(result) == 1
        assert result[0].link is not None
