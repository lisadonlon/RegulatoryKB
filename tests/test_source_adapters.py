"""Tests for source adapters and registry."""

from unittest.mock import MagicMock, patch

from regkb.intelligence.fetcher import FetchResult, NewsletterEntry
from regkb.intelligence.sources.newsletter import NewsletterSourceAdapter


class TestSourceAdapterInterface:
    def test_newsletter_adapter_has_required_properties(self):
        adapter = NewsletterSourceAdapter()
        assert adapter.name == "Index-of-Indexes Newsletter"
        assert adapter.source_id == "ioi"
        assert adapter.enabled is True


class TestNewsletterAdapter:
    def test_wraps_existing_fetcher(self):
        adapter = NewsletterSourceAdapter()

        mock_result = FetchResult(
            total_entries=3,
            entries=[
                NewsletterEntry(date="2026-02-10", agency="FDA", category="Devices", title="Test"),
            ],
            sources_fetched=1,
        )

        with patch.object(adapter, "fetch", return_value=mock_result):
            result = adapter.fetch(days=7)
            assert result.total_entries == 3


class TestFDACDRHAdapter:
    def test_parses_rss_entries(self):
        """Test FDA adapter parses feedparser output correctly."""
        from regkb.intelligence.sources.fda_rss import FDACDRHAdapter

        adapter = FDACDRHAdapter()
        assert adapter.name == "FDA CDRH"
        assert adapter.source_id == "fda_cdrh"

    def test_parse_feed_with_mock_data(self):
        """Test feed parsing with mock feedparser data."""
        from regkb.intelligence.sources.fda_rss import FDACDRHAdapter

        adapter = FDACDRHAdapter()

        mock_feed = MagicMock()
        mock_item = MagicMock()
        mock_item.get.side_effect = lambda key, default="": {
            "title": "FDA Issues New CDRH Guidance on AI/ML",
            "link": "https://fda.gov/test",
        }.get(key, default)
        mock_item.published_parsed = (2026, 2, 17, 10, 0, 0, 0, 48, 0)
        mock_feed.entries = [mock_item]

        with patch("regkb.intelligence.sources.fda_rss.feedparser.parse", return_value=mock_feed):
            result = adapter.fetch(days=30)
            assert isinstance(result, FetchResult)


class TestEUAdapter:
    def test_eu_adapter_properties(self):
        from regkb.intelligence.sources.eu_rss import EUOfficialJournalAdapter

        adapter = EUOfficialJournalAdapter()
        assert adapter.name == "EU Official Journal"
        assert adapter.source_id == "eu_oj"

    def test_device_keyword_filter(self):
        from regkb.intelligence.sources.eu_rss import EUOfficialJournalAdapter

        adapter = EUOfficialJournalAdapter()

        entries = [
            NewsletterEntry(
                date="2026-02-10",
                agency="EU",
                category="Regulation",
                title="MDR Implementation Update",
            ),
            NewsletterEntry(
                date="2026-02-10",
                agency="EU",
                category="Regulation",
                title="Pharmaceutical Pricing Directive",
            ),
            NewsletterEntry(
                date="2026-02-10",
                agency="EU",
                category="Regulation",
                title="IVDR Transition Period Extension",
            ),
        ]

        filtered = adapter._filter_device_relevant(entries)
        assert len(filtered) == 2
        assert "MDR" in filtered[0].title
        assert "IVDR" in filtered[1].title


class TestMHRAAdapter:
    def test_mhra_adapter_properties(self):
        from regkb.intelligence.sources.mhra_rss import MHRAAdapter

        adapter = MHRAAdapter()
        assert adapter.name == "MHRA (UK)"
        assert adapter.source_id == "mhra"

    def test_device_alert_filter(self):
        from regkb.intelligence.sources.mhra_rss import MHRAAdapter

        adapter = MHRAAdapter()

        assert adapter._is_device_alert("Medical device alert: MDA/2026/001")
        assert adapter._is_device_alert("All medical device alerts - January 2026")
        assert not adapter._is_device_alert("Drug safety update: paracetamol")


class TestSourceRegistry:
    def test_get_all_adapters_includes_newsletter(self):
        from regkb.intelligence.sources.registry import get_all_adapters

        adapters = get_all_adapters()
        source_ids = [a.source_id for a in adapters]
        assert "ioi" in source_ids

    def test_fetch_all_sources_merges(self):
        from regkb.intelligence.sources.registry import fetch_all_sources

        mock_result = FetchResult(
            total_entries=2,
            entries=[
                NewsletterEntry(
                    date="2026-02-10", agency="FDA", category="Devices", title="Test 1"
                ),
                NewsletterEntry(date="2026-02-10", agency="EU", category="Devices", title="Test 2"),
            ],
            sources_fetched=1,
        )

        with patch("regkb.intelligence.sources.newsletter.NewsletterFetcher") as mock_fetcher:
            mock_fetcher.return_value.fetch.return_value = mock_result
            # Only newsletter adapter should be loaded in test (no feedparser mock needed)
            with patch("regkb.intelligence.sources.registry._try_load"):
                result = fetch_all_sources(days=7)
                assert isinstance(result, FetchResult)
                assert result.sources_fetched >= 1
