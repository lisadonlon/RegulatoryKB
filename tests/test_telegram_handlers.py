"""Tests for Telegram bot command handlers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from regkb.telegram.handlers import (
    digest_command,
    help_command,
    pending_command,
    search_command,
    start_command,
    status_command,
)


@pytest.fixture
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.effective_user.id = 12345
    update.effective_user.username = "testuser"
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    context.args = []
    return context


class TestStartCommand:
    @pytest.mark.asyncio
    async def test_sends_welcome(self, mock_update, mock_context):
        await start_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "Welcome" in text or "RegKB" in text


class TestHelpCommand:
    @pytest.mark.asyncio
    async def test_sends_command_list(self, mock_update, mock_context):
        await help_command(mock_update, mock_context)
        mock_update.message.reply_text.assert_called()
        text = mock_update.message.reply_text.call_args[0][0]
        assert "/status" in text
        assert "/digest" in text
        assert "/search" in text


class TestStatusCommand:
    @pytest.mark.asyncio
    async def test_status_shows_stats(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        with patch("regkb.telegram.handlers._get_db_stats", return_value={"total_documents": 130}):
            with patch("regkb.telegram.handlers._get_pending_count", return_value=5):
                await status_command(mock_update, mock_context)

        # First call is "Loading...", second is the actual stats
        assert mock_update.message.reply_text.call_count >= 2

    @pytest.mark.asyncio
    async def test_status_handles_error(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        with patch("regkb.telegram.handlers._get_db_stats", side_effect=Exception("DB error")):
            await status_command(mock_update, mock_context)

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "Error" in last_call[0][0]


class TestDigestCommand:
    @pytest.mark.asyncio
    async def test_digest_no_entries(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        with patch("regkb.telegram.handlers._run_digest_pipeline", return_value=[]):
            await digest_command(mock_update, mock_context)

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "No relevant" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_digest_with_entries(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        mock_entry = MagicMock()
        mock_entry.entry.title = "FDA Issues New Guidance"
        mock_entry.entry.agency = "FDA"
        mock_entry.entry.category = "Medical Devices"
        mock_entry.entry.date = "2026-02-17"
        mock_entry.entry.link = "https://fda.gov/test"
        mock_entry.alert_level = None
        mock_entry.matched_keywords = ["FDA", "guidance"]

        with patch("regkb.telegram.handlers._run_digest_pipeline", return_value=[mock_entry]):
            await digest_command(mock_update, mock_context)

        # Should have loading message + actual digest
        assert mock_update.message.reply_text.call_count >= 2


class TestSearchCommand:
    @pytest.mark.asyncio
    async def test_search_no_query(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")
        mock_context.args = []

        await search_command(mock_update, mock_context)

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "Usage" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_search_with_results(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")
        mock_context.args = ["cybersecurity", "guidance"]

        results = [
            {"title": "FDA Cybersecurity Guidance", "jurisdiction": "FDA", "score": 0.85},
        ]

        with patch("regkb.telegram.handlers._run_search", return_value=results):
            await search_command(mock_update, mock_context)

        assert mock_update.message.reply_text.call_count >= 1


class TestPendingCommand:
    @pytest.mark.asyncio
    async def test_pending_empty(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        with patch("regkb.telegram.handlers._get_pending_items", return_value=[]):
            await pending_command(mock_update, mock_context)

        last_call = mock_update.message.reply_text.call_args_list[-1]
        assert "No pending" in last_call[0][0]

    @pytest.mark.asyncio
    async def test_pending_with_items(self, mock_update, mock_context, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        item = MagicMock()
        item.id = 1
        item.title = "Test Document"
        item.agency = "FDA"
        item.relevance_score = 0.8

        with patch("regkb.telegram.handlers._get_pending_items", return_value=[item]):
            await pending_command(mock_update, mock_context)

        # Should have header + item messages
        assert mock_update.message.reply_text.call_count >= 2
