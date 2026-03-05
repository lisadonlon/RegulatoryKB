"""Tests for scheduler job definitions."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from regkb.scheduler.jobs import _is_auth_failure


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


class TestIsAuthFailure:
    def test_detects_authentication_keyword(self):
        assert _is_auth_failure(Exception("Authentication failed")) is True

    def test_detects_expired_keyword(self):
        assert _is_auth_failure(Exception("Session expired")) is True

    def test_detects_login_keyword(self):
        assert _is_auth_failure(Exception("Please login again")) is True

    def test_detects_storage_state_keyword(self):
        assert _is_auth_failure(Exception("storage_state.json not found")) is True

    def test_ignores_unrelated_error(self):
        assert _is_auth_failure(Exception("Network timeout")) is False

    def test_case_insensitive(self):
        assert _is_auth_failure(Exception("AUTHENTICATION ERROR")) is True


class TestNotebooklmKeepaliveJob:
    @pytest.mark.asyncio
    async def test_skips_when_disabled(self):
        from regkb.scheduler.jobs import notebooklm_keepalive_job

        mock_config = MagicMock()
        mock_config.get.return_value = False

        with patch("regkb.scheduler.jobs.asyncio.to_thread") as mock_thread:
            with patch("regkb.config.config", mock_config):
                await notebooklm_keepalive_job()
            mock_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_auth_success_logs_alive(self):
        from regkb.scheduler.jobs import notebooklm_keepalive_job

        mock_config = MagicMock()
        mock_config.get.return_value = True

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=True):
            with patch("regkb.config.config", mock_config):
                await notebooklm_keepalive_job()

    @pytest.mark.asyncio
    async def test_auth_failure_sends_telegram_alert(self):
        from regkb.scheduler.jobs import notebooklm_keepalive_job

        mock_config = MagicMock()
        mock_config.get.return_value = True

        mock_notify = AsyncMock()

        with patch("regkb.scheduler.jobs.asyncio.to_thread", return_value=False):
            with patch("regkb.config.config", mock_config):
                with patch(
                    "regkb.telegram.notifications.notify_notebooklm_auth_failure",
                    mock_notify,
                ):
                    await notebooklm_keepalive_job()

        mock_notify.assert_awaited_once_with("Keep-Alive Check")

    @pytest.mark.asyncio
    async def test_exception_with_auth_keyword_sends_alert(self):
        from regkb.scheduler.jobs import notebooklm_keepalive_job

        mock_config = MagicMock()
        mock_config.get.return_value = True

        mock_notify = AsyncMock()

        with patch(
            "regkb.scheduler.jobs.asyncio.to_thread",
            side_effect=Exception("authentication expired"),
        ):
            with patch("regkb.config.config", mock_config):
                with patch(
                    "regkb.telegram.notifications.notify_notebooklm_auth_failure",
                    mock_notify,
                ):
                    await notebooklm_keepalive_job()

        mock_notify.assert_awaited_once_with("Keep-Alive Check")


class TestNotebooklmExportAuthAlert:
    @pytest.mark.asyncio
    async def test_auth_failure_triggers_telegram(self):
        from regkb.scheduler.jobs import _trigger_notebooklm_export

        mock_config = MagicMock()
        mock_config.get.side_effect = lambda key, default=None: {
            "intelligence.notebooklm.auto_generate": True,
            "intelligence.notebooklm.artifact_types": ["report"],
        }.get(key, default)

        mock_notify = AsyncMock()

        with patch(
            "regkb.scheduler.jobs.asyncio.to_thread",
            side_effect=Exception("Session expired"),
        ):
            with patch("regkb.config.config", mock_config):
                with patch(
                    "regkb.telegram.notifications.notify_notebooklm_auth_failure",
                    mock_notify,
                ):
                    await _trigger_notebooklm_export()

        mock_notify.assert_awaited_once_with("NotebookLM Export")
