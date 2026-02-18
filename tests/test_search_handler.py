"""Tests for enhanced search handler with NL parsing and LLM integration."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from regkb.telegram.search_handler import parse_query


class TestParseQuery:
    def test_extracts_fda_jurisdiction(self):
        result = parse_query("FDA cybersecurity guidance")
        assert result["jurisdiction"] == "FDA"
        assert "cybersecurity" in result["query"]

    def test_extracts_eu_jurisdiction(self):
        result = parse_query("EU MDR documents")
        assert result["jurisdiction"] == "EU"

    def test_extracts_uk_jurisdiction(self):
        result = parse_query("UK safety alerts")
        assert result["jurisdiction"] == "UK"

    def test_extracts_iso_jurisdiction(self):
        result = parse_query("ISO 13485")
        assert result["jurisdiction"] == "ISO"
        assert "13485" in result["query"]

    def test_extracts_document_type(self):
        result = parse_query("FDA cybersecurity guidance")
        assert result["document_type"] == "guidance"

    def test_extracts_standard_type(self):
        result = parse_query("ISO standard for quality management")
        assert result["document_type"] == "standard"

    def test_no_filters(self):
        result = parse_query("cybersecurity requirements")
        assert result["jurisdiction"] is None
        assert result["document_type"] is None
        assert "cybersecurity" in result["query"]

    def test_strips_question_phrasing(self):
        result = parse_query("What FDA guidance do we have?")
        assert result["jurisdiction"] == "FDA"

    def test_mhra_alias(self):
        result = parse_query("MHRA device alerts")
        assert result["jurisdiction"] == "UK"

    def test_hpra_alias(self):
        result = parse_query("HPRA medical device guidance")
        assert result["jurisdiction"] == "Ireland"

    def test_canada_alias(self):
        result = parse_query("Canadian medical device regulations")
        assert result["jurisdiction"] == "Health Canada"

    def test_tga_alias(self):
        result = parse_query("TGA guidance on software")
        assert result["jurisdiction"] == "TGA"

    def test_preserves_query_when_all_parsed(self):
        result = parse_query("FDA guidance")
        # Should not return empty query
        assert result["query"]


class TestEnhancedSearchCommand:
    @pytest.mark.asyncio
    async def test_no_query_shows_usage(self, monkeypatch):
        from regkb.telegram.search_handler import enhanced_search_command

        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await enhanced_search_command(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Usage" in text

    @pytest.mark.asyncio
    async def test_with_results(self, monkeypatch):
        from regkb.telegram.search_handler import enhanced_search_command

        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = ["FDA", "cybersecurity"]

        results = [
            {"title": "FDA Cybersecurity Guidance", "jurisdiction": "FDA", "score": 0.9},
        ]

        with patch("regkb.telegram.search_handler._run_filtered_search", return_value=results):
            await enhanced_search_command(update, context)

        # Should have filter note + results
        assert update.message.reply_text.call_count >= 2


class TestAskCommand:
    @pytest.mark.asyncio
    async def test_no_question_shows_usage(self, monkeypatch):
        from regkb.telegram.search_handler import ask_command

        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = []

        await ask_command(update, context)

        text = update.message.reply_text.call_args[0][0]
        assert "Usage" in text

    @pytest.mark.asyncio
    async def test_falls_back_to_search(self, monkeypatch):
        from regkb.telegram.search_handler import ask_command

        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        context = MagicMock()
        context.args = ["What", "FDA", "guidance", "do", "we", "have?"]

        # Mock ImportError for llm_handler to test fallback
        with patch("regkb.telegram.search_handler.enhanced_search_command", new_callable=AsyncMock):
            with patch.dict("sys.modules", {"regkb.telegram.llm_handler": None}):
                # The ImportError path should call enhanced_search_command
                await ask_command(update, context)
