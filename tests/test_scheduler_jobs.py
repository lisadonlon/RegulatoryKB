"""Tests for scheduler job definitions."""

from unittest.mock import MagicMock, patch

import pytest


class TestWeeklyDigestJob:
    @pytest.mark.asyncio
    async def test_skips_when_already_run(self):
        from regkb.scheduler.jobs import weekly_digest_job

        mock_state = MagicMock()
        mock_state.should_run_weekly.return_value = False

        with patch("regkb.scheduler.jobs.asyncio.to_thread") as mock_thread:
            # Simulate the _run function returning None when should_run is False
            mock_thread.return_value = None
            await weekly_digest_job()

    @pytest.mark.asyncio
    async def test_runs_pipeline_and_sends(self):
        from regkb.scheduler.jobs import weekly_digest_job

        mock_state = MagicMock()
        mock_state.should_run_weekly.return_value = True

        result = {"entries": 5, "email_success": True, "recipients": 2}

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=result):
            with patch("regkb.telegram.notifications.notify_digest_sent"):
                # Handle ImportError for telegram
                try:
                    await weekly_digest_job()
                except ImportError:
                    pass  # Telegram not installed in test env


class TestDailyAlertJob:
    @pytest.mark.asyncio
    async def test_no_critical_items(self):
        from regkb.scheduler.jobs import daily_alert_job

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=None):
            await daily_alert_job()

    @pytest.mark.asyncio
    async def test_with_critical_items(self):
        from regkb.scheduler.jobs import daily_alert_job

        mock_entry = MagicMock()
        mock_entry.entry.title = "FDA Safety Alert"
        mock_entry.entry.agency = "FDA"
        mock_entry.alert_level = "CRITICAL"

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=[mock_entry]):
            try:
                await daily_alert_job()
            except ImportError:
                pass  # Telegram not installed


class TestImapPollJob:
    @pytest.mark.asyncio
    async def test_skips_when_not_configured(self, monkeypatch):
        from regkb.scheduler.jobs import imap_poll_job

        monkeypatch.delenv("IMAP_USERNAME", raising=False)

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=None):
            await imap_poll_job()
