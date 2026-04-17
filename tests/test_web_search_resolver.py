"""Tests for web_search_resolver — web search fallback for LinkedIn URLs."""

from unittest.mock import MagicMock, patch

from regkb.intelligence.web_search_resolver import (
    _extract_url,
    _is_on_trusted_domain,
    web_search,
    web_search_resolve,
)

TRUSTED = ["fda.gov", "canada.ca", "health-products.canada.ca"]


# ---------------------------------------------------------------------------
# Unit: web_search tool
# ---------------------------------------------------------------------------


class TestWebSearchTool:
    @patch("regkb.intelligence.web_search_resolver.DDGS")
    def test_returns_structured_results(self, mock_ddgs_cls):
        mock_ddgs_cls.return_value.text.return_value = [
            {
                "title": "FDA Guidance",
                "href": "https://www.fda.gov/doc.pdf",
                "body": "Official guidance document",
            },
            {
                "title": "Other",
                "href": "https://example.com/other",
                "body": "Not relevant",
            },
        ]
        results = web_search("FDA guidance on AI", max_results=5)
        assert len(results) == 2
        assert results[0]["title"] == "FDA Guidance"
        assert results[0]["url"] == "https://www.fda.gov/doc.pdf"
        assert results[0]["snippet"] == "Official guidance document"

    @patch("regkb.intelligence.web_search_resolver.DDGS")
    def test_handles_ddgs_exception(self, mock_ddgs_cls):
        mock_ddgs_cls.return_value.text.side_effect = Exception("Network error")
        results = web_search("test query")
        assert results == []


# ---------------------------------------------------------------------------
# Unit: domain validation
# ---------------------------------------------------------------------------


class TestDomainValidation:
    def test_trusted_domain_matches(self):
        assert _is_on_trusted_domain("https://www.fda.gov/doc.pdf", TRUSTED)

    def test_subdomain_matches(self):
        assert _is_on_trusted_domain("https://health-products.canada.ca/item/123", TRUSTED)

    def test_untrusted_domain_rejected(self):
        assert not _is_on_trusted_domain("https://linkedin.com/post/123", TRUSTED)

    def test_empty_url(self):
        assert not _is_on_trusted_domain("", TRUSTED)


# ---------------------------------------------------------------------------
# Unit: URL extraction
# ---------------------------------------------------------------------------


class TestExtractUrl:
    def test_extracts_url_from_text(self):
        assert (
            _extract_url("The document is at https://fda.gov/doc.pdf here.")
            == "https://fda.gov/doc.pdf"
        )

    def test_strips_trailing_punctuation(self):
        assert _extract_url("https://fda.gov/doc.pdf.") == "https://fda.gov/doc.pdf"

    def test_returns_none_for_no_url(self):
        assert _extract_url("NOT_FOUND") is None


# ---------------------------------------------------------------------------
# Integration: web_search_resolve orchestrator
# ---------------------------------------------------------------------------


class TestWebSearchResolve:
    @patch("regkb.intelligence.web_search_resolver._call_ollama")
    @patch("regkb.intelligence.web_search_resolver.DDGS")
    def test_finds_trusted_url(self, mock_ddgs_cls, mock_ollama):
        """LLM calls web_search, then returns a trusted URL."""
        mock_ddgs_cls.return_value.text.return_value = [
            {
                "title": "Health Canada Guidance",
                "href": "https://health-products.canada.ca/doc/123",
                "body": "Summary reports guidance",
            },
        ]

        # Turn 1: LLM calls web_search tool
        mock_ollama.side_effect = [
            {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "web_search",
                            "arguments": {"query": "Health Canada summary reports guidance"},
                        }
                    }
                ],
            },
            # Turn 2: LLM returns the URL
            {
                "content": "https://health-products.canada.ca/doc/123",
                "tool_calls": [],
            },
        ]

        result = web_search_resolve(
            title="Summary Reports Guidance",
            agency="Health Canada",
            trusted_domains=TRUSTED,
        )
        assert result == "https://health-products.canada.ca/doc/123"

    @patch("regkb.intelligence.web_search_resolver._call_ollama")
    def test_rejects_untrusted_url(self, mock_ollama):
        """LLM returns a URL not on a trusted domain -> returns None."""
        mock_ollama.return_value = {
            "content": "https://random-blog.com/regulatory-news",
            "tool_calls": [],
        }
        result = web_search_resolve(
            title="Some Guidance",
            agency="FDA",
            trusted_domains=TRUSTED,
        )
        assert result is None

    @patch("regkb.intelligence.web_search_resolver._call_ollama")
    @patch("regkb.intelligence.web_search_resolver.DDGS")
    def test_handles_no_results(self, mock_ddgs_cls, mock_ollama):
        """Empty search results -> LLM says NOT_FOUND -> returns None."""
        mock_ddgs_cls.return_value.text.return_value = []

        mock_ollama.side_effect = [
            # Turn 1: LLM calls search
            {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "web_search",
                            "arguments": {"query": "test query"},
                        }
                    }
                ],
            },
            # Turn 2: LLM says not found
            {"content": "NOT_FOUND", "tool_calls": []},
        ]

        result = web_search_resolve(
            title="Nonexistent Doc",
            agency="Unknown",
            trusted_domains=TRUSTED,
        )
        assert result is None

    @patch("regkb.intelligence.web_search_resolver._call_ollama")
    @patch("regkb.intelligence.web_search_resolver.DDGS")
    def test_max_turns_respected(self, mock_ddgs_cls, mock_ollama):
        """LLM keeps calling tools -> stops at max_turns."""
        mock_ddgs_cls.return_value.text.return_value = [
            {"title": "Result", "href": "https://example.com", "body": "..."}
        ]

        # LLM always calls tool, never produces final answer
        mock_ollama.return_value = {
            "content": "",
            "tool_calls": [
                {
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": "keep searching"},
                    }
                }
            ],
        }

        result = web_search_resolve(
            title="Elusive Doc",
            agency="FDA",
            trusted_domains=TRUSTED,
            max_turns=3,
        )
        assert result is None
        assert mock_ollama.call_count == 3

    @patch("regkb.intelligence.web_search_resolver._call_ollama")
    def test_handles_ollama_error(self, mock_ollama):
        """Ollama HTTP error -> returns None gracefully."""
        import httpx

        mock_ollama.side_effect = httpx.HTTPError("Connection refused")
        result = web_search_resolve(
            title="Some Doc",
            agency="FDA",
            trusted_domains=TRUSTED,
        )
        assert result is None


# ---------------------------------------------------------------------------
# Integration: reply_handler uses web search fallback
# ---------------------------------------------------------------------------


class TestReplyHandlerWebSearchFallback:
    @patch("regkb.intelligence.reply_handler.web_search_resolve")
    @patch("regkb.intelligence.reply_handler.url_resolver")
    @patch("regkb.intelligence.reply_handler.digest_tracker")
    def test_web_search_fallback_on_needs_manual(
        self, mock_tracker, mock_resolver, mock_ws_resolve
    ):
        """When url_resolver returns needs_manual, web search is attempted."""
        from regkb.intelligence.reply_handler import (
            DownloadRequest,
            ReplyHandler,
        )
        from regkb.intelligence.url_resolver import ResolveResult

        # Setup: url_resolver says needs_manual
        mock_resolve_result = ResolveResult(
            success=False,
            original_url="https://linkedin.com/post/123",
            needs_manual=True,
        )
        mock_resolver.resolve.return_value = mock_resolve_result
        mock_resolver.trusted_domains = {"fda.gov", "canada.ca"}

        # Web search finds a URL
        mock_ws_resolve.return_value = "https://www.fda.gov/found-doc.pdf"

        # Mock entry lookup
        entry = MagicMock()
        entry.entry_id = "2026-0413-07"
        entry.title = "Test Guidance"
        entry.agency = "FDA"
        entry.link = "https://linkedin.com/post/123"
        entry.download_status = "pending"
        mock_tracker.lookup_entries.return_value = [entry]

        # Mock the importer to succeed
        with patch("regkb.importer.importer") as mock_imp:
            mock_imp.import_from_url.return_value = 42
            mock_imp.last_version_diff = None
            mock_imp.last_content_warning = None

            handler = ReplyHandler.__new__(ReplyHandler)
            handler.config = MagicMock()
            handler.allowed_senders = set()
            handler._processed_ids = set()

            request = DownloadRequest(
                entry_ids=["07"],
                requester_email="test@test.com",
                subject="Re: Regulatory Intelligence Weekly",
                received_at=MagicMock(),
                raw_body="Download: 07",
            )

            results = handler.process_request(request)

        # web_search_resolve was called
        mock_ws_resolve.assert_called_once_with(
            title=entry.title,
            agency=entry.agency,
            trusted_domains=list(mock_resolver.trusted_domains),
        )

        # Download was attempted with the found URL
        assert len(results) == 1
        assert results[0].success is True
        assert results[0].resolved_url == "https://www.fda.gov/found-doc.pdf"
