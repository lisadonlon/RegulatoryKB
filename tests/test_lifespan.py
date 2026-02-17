"""Tests for the FastAPI lifespan context manager."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestLifespan:
    @pytest.mark.asyncio
    async def test_lifespan_sets_started_at(self):
        """Lifespan sets app.state.started_at on startup."""
        from regkb.web.lifespan import lifespan

        app = MagicMock()
        app.state = MagicMock()

        async with lifespan(app):
            assert isinstance(app.state.started_at, datetime)

    @pytest.mark.asyncio
    async def test_lifespan_defaults_none_without_config(self):
        """Without scheduler/telegram config, both are None."""
        from regkb.web.lifespan import lifespan

        app = MagicMock()
        app.state = MagicMock()

        with patch("regkb.web.lifespan._start_scheduler", return_value=None):
            with patch(
                "regkb.web.lifespan._start_telegram_bot", new_callable=AsyncMock, return_value=None
            ):
                async with lifespan(app):
                    assert app.state.scheduler is None
                    assert app.state.telegram_app is None

    @pytest.mark.asyncio
    async def test_lifespan_starts_scheduler_when_configured(self):
        """Lifespan starts scheduler when create_scheduler returns one."""
        from regkb.web.lifespan import lifespan

        mock_scheduler = MagicMock()
        app = MagicMock()
        app.state = MagicMock()

        with patch("regkb.web.lifespan._start_scheduler", return_value=mock_scheduler):
            with patch(
                "regkb.web.lifespan._start_telegram_bot", new_callable=AsyncMock, return_value=None
            ):
                async with lifespan(app):
                    assert app.state.scheduler is mock_scheduler

        # Verify shutdown was called
        mock_scheduler.shutdown.assert_called_once_with(wait=False)

    @pytest.mark.asyncio
    async def test_lifespan_starts_telegram_when_configured(self):
        """Lifespan starts Telegram bot when token is available."""
        from regkb.web.lifespan import lifespan

        mock_telegram = AsyncMock()
        app = MagicMock()
        app.state = MagicMock()

        with patch("regkb.web.lifespan._start_scheduler", return_value=None):
            with patch(
                "regkb.web.lifespan._start_telegram_bot",
                new_callable=AsyncMock,
                return_value=mock_telegram,
            ):
                async with lifespan(app):
                    assert app.state.telegram_app is mock_telegram

        # Verify shutdown was called
        mock_telegram.stop.assert_called_once()
        mock_telegram.shutdown.assert_called_once()
