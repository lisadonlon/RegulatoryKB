"""Tests for Telegram bot authentication."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from regkb.telegram.auth import get_authorized_users, require_auth


class TestGetAuthorizedUsers:
    def test_empty_env(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_AUTHORIZED_USERS", raising=False)
        assert get_authorized_users() == set()

    def test_single_user(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")
        assert get_authorized_users() == {12345}

    def test_multiple_users(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345,67890,11111")
        assert get_authorized_users() == {12345, 67890, 11111}

    def test_whitespace_handling(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", " 12345 , 67890 ")
        assert get_authorized_users() == {12345, 67890}

    def test_invalid_format(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "abc,def")
        assert get_authorized_users() == set()


class TestRequireAuth:
    @pytest.mark.asyncio
    async def test_authorized_user_passes(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        @require_auth
        async def handler(update, context):
            return "ok"

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        result = await handler(update, MagicMock())
        assert result == "ok"

    @pytest.mark.asyncio
    async def test_unauthorized_user_blocked(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_AUTHORIZED_USERS", "12345")

        @require_auth
        async def handler(update, context):
            return "ok"

        update = MagicMock()
        update.effective_user.id = 99999
        update.message.reply_text = AsyncMock()

        result = await handler(update, MagicMock())
        assert result is None
        update.message.reply_text.assert_called_once()
        assert "not authorized" in update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_no_users_configured(self, monkeypatch):
        monkeypatch.delenv("TELEGRAM_AUTHORIZED_USERS", raising=False)

        @require_auth
        async def handler(update, context):
            return "ok"

        update = MagicMock()
        update.effective_user.id = 12345
        update.message.reply_text = AsyncMock()

        result = await handler(update, MagicMock())
        assert result is None
        update.message.reply_text.assert_called_once()
