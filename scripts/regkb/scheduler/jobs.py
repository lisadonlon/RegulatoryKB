"""
Scheduled job definitions for the RegKB intelligence pipeline.

All jobs are async functions that wrap synchronous pipeline calls
in asyncio.to_thread(). Each job checks SchedulerState for idempotency.
"""

import asyncio
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

_AUTH_FAILURE_KEYWORDS = ("authentication", "expired", "login", "auth", "storage_state")


def _is_auth_failure(exc: Exception) -> bool:
    """Check if an exception is likely a NotebookLM auth expiry."""
    msg = str(exc).lower()
    return any(kw in msg for kw in _AUTH_FAILURE_KEYWORDS)


async def weekly_digest_job():
    """Fetch, filter, and send weekly digest via email and Telegram.

    Uses SchedulerState.should_run_weekly() for idempotency — if the digest
    was already sent this week (e.g., manual trigger), this is a no-op.
    """
    logger.info("Weekly digest job started")

    def _run():
        from regkb.intelligence.scheduler import SchedulerState

        state = SchedulerState()
        if not state.should_run_weekly():
            logger.info("Weekly digest already sent this period — skipping")
            return None

        from regkb.intelligence.fetcher import NewsletterFetcher
        from regkb.intelligence.filter import ContentFilter

        # Try multi-source if available, fallback to newsletter only
        try:
            from regkb.intelligence.sources.registry import fetch_all_sources

            fetch_result = fetch_all_sources(days=7)
        except ImportError:
            fetcher = NewsletterFetcher()
            fetch_result = fetcher.fetch(days=7)

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        if filter_result.total_included == 0:
            logger.info("No relevant entries for weekly digest")
            state.mark_weekly_run()
            return None

        # Send email
        from regkb.intelligence.emailer import Emailer

        emailer = Emailer()
        entries_with_summaries = [(fe, None) for fe in filter_result.included]
        high_priority = [(fe, None) for fe in filter_result.high_priority]

        end = datetime.now()
        start = end - timedelta(days=7)
        date_range = f"{start.strftime('%d %b')} - {end.strftime('%d %b %Y')}"

        email_result = emailer.send_weekly_digest(
            entries_with_summaries=entries_with_summaries,
            high_priority=high_priority,
            date_range=date_range,
        )

        state.mark_weekly_run()
        return {
            "entries": filter_result.total_included,
            "email_success": email_result.success,
            "recipients": email_result.recipients_sent,
        }

    result = await asyncio.to_thread(_run)

    if result:
        logger.info(
            "Weekly digest complete: %d entries, email=%s, recipients=%d",
            result["entries"],
            result["email_success"],
            result["recipients"],
        )

        # Send Telegram notification
        try:
            from regkb.telegram.notifications import notify_digest_sent

            await notify_digest_sent(result["entries"], result["recipients"])
        except ImportError:
            pass

        # Trigger NotebookLM export if enabled and digest was sent successfully
        if result["email_success"]:
            await _trigger_notebooklm_export()


async def _trigger_notebooklm_export():
    """Generate NotebookLM artifacts from latest digest (non-fatal, config-gated)."""
    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.auto_generate", False):
            return

        artifact_types = config.get("intelligence.notebooklm.artifact_types", ["report"])

        def _run_export():
            from regkb.notebooklm_export import run_pipeline

            return run_pipeline(days=7, artifact_types=artifact_types)

        result = await asyncio.to_thread(_run_export)
        logger.info("NotebookLM export complete: %s", result)
    except Exception as exc:
        logger.exception("NotebookLM export failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("NotebookLM Export")
            except ImportError:
                pass


async def daily_alert_job():
    """Check for critical/high-priority items and send alerts.

    Only sends if new critical items are found since last daily run.
    """
    logger.info("Daily alert job started")

    def _run():
        from regkb.intelligence.scheduler import SchedulerState

        state = SchedulerState()
        if not state.should_run_daily():
            logger.info("Daily alert already run today — skipping")
            return None

        from regkb.intelligence.fetcher import NewsletterFetcher
        from regkb.intelligence.filter import ContentFilter

        # Try multi-source if available
        try:
            from regkb.intelligence.sources.registry import fetch_all_sources

            fetch_result = fetch_all_sources(days=1)
        except ImportError:
            fetcher = NewsletterFetcher()
            fetch_result = fetcher.fetch(days=1)

        content_filter = ContentFilter()
        filter_result = content_filter.filter(fetch_result.entries)

        state.mark_daily_run()

        critical = [e for e in filter_result.included if e.alert_level in ("CRITICAL", "HIGH")]
        return critical

    critical = await asyncio.to_thread(_run)

    if critical:
        logger.info("Daily alert: %d critical/high items found", len(critical))

        # Send Telegram push for each critical item
        try:
            from regkb.telegram.notifications import notify_critical_alert

            for entry in critical:
                await notify_critical_alert(
                    title=entry.entry.title,
                    agency=entry.entry.agency or "",
                )
        except ImportError:
            pass
    else:
        logger.info("Daily alert: no critical items")


async def imap_poll_job():
    """Poll IMAP inbox for download request replies."""
    logger.info("IMAP poll job started")

    def _run():
        import os

        # Check if IMAP credentials are configured
        if not os.environ.get("IMAP_USERNAME"):
            logger.debug("IMAP not configured — skipping poll")
            return None

        from regkb.intelligence.reply_handler import ReplyHandler

        handler = ReplyHandler()
        result = handler.process_all_pending()
        return result

    result = await asyncio.to_thread(_run)

    if result:
        logger.info("IMAP poll complete: %s", result)


async def monthly_competitive_refresh_job():
    """Refresh competitive intelligence via NotebookLM (non-fatal, config-gated).

    Runs on 1st of each month. Calls PraxisVerify's refresh_insights() via
    sys.path import since PraxisVerify has no scheduler of its own.
    """
    logger.info("Monthly competitive refresh job started")

    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.competitive_refresh.enabled", False):
            logger.info("Competitive refresh not enabled — skipping")
            return

        def _run():
            praxisverify_scripts = str(
                Path(__file__).resolve().parents[4] / "PraxisVerify" / "scripts"
            )
            if praxisverify_scripts not in sys.path:
                sys.path.insert(0, praxisverify_scripts)

            from notebooklm_competitive import refresh_insights

            return refresh_insights()

        result = await asyncio.to_thread(_run)
        logger.info("Competitive refresh complete: success=%s", result)
    except Exception as exc:
        logger.exception("Monthly competitive refresh failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("Monthly Competitive Refresh")
            except ImportError:
                pass


async def training_mcq_job():
    """Generate MCQs for stale/missing training topics (non-fatal, config-gated).

    Runs weekly (Sunday evening). Only generates for topics where the MCQ JSON
    file is older than refresh_days or missing.
    """
    logger.info("Training MCQ job started")

    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.training.enabled", False):
            logger.info("Training MCQ generation not enabled — skipping")
            return

        topics = config.get("intelligence.notebooklm.training.topics", ["eu-mdr-gspr"])
        refresh_days = config.get("intelligence.notebooklm.training.refresh_days", 30)

        def _run():
            medtech_scripts = str(Path(__file__).resolve().parents[4] / "medtech-docs" / "scripts")
            if medtech_scripts not in sys.path:
                sys.path.insert(0, medtech_scripts)

            from notebooklm_training import MCQ_OUTPUT_DIR, mcq_pipeline

            generated = []
            for topic in topics:
                mcq_path = MCQ_OUTPUT_DIR / f"{topic}_mcqs.json"
                if mcq_path.exists():
                    age_days = (
                        datetime.now() - datetime.fromtimestamp(mcq_path.stat().st_mtime)
                    ).days
                    if age_days < refresh_days:
                        logger.info(
                            "Topic %s MCQs are fresh (%d days old) — skipping",
                            topic,
                            age_days,
                        )
                        continue

                logger.info("Generating MCQs for topic: %s", topic)
                result = mcq_pipeline(topic)
                if result:
                    generated.append(topic)

            return generated

        generated = await asyncio.to_thread(_run)
        logger.info("Training MCQ generation complete: %s", generated)
    except Exception as exc:
        logger.exception("Training MCQ generation failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("Training MCQ Generation")
            except ImportError:
                pass


async def youtube_research_job():
    """Fetch new YouTube videos and generate NotebookLM artifacts (non-fatal, config-gated).

    Runs weekly. Calls AIfirst's youtube_research agent via sys.path import.
    """
    logger.info("YouTube research job started")

    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.youtube_research.enabled", False):
            logger.info("YouTube research not enabled — skipping")
            return

        days_back = config.get("intelligence.notebooklm.youtube_research.days_back", 7)

        def _run():
            aifirst_root = str(Path(__file__).resolve().parents[4] / "AIfirst")
            if aifirst_root not in sys.path:
                sys.path.insert(0, aifirst_root)

            # Also ensure shared_lib is importable
            projects_root = str(Path(__file__).resolve().parents[4])
            if projects_root not in sys.path:
                sys.path.insert(0, projects_root)

            from agents.youtube_research.config import CHANNELS
            from agents.youtube_research.fetcher import YouTubeFetcher
            from agents.youtube_research.main import (
                run_pipeline,
                save_synthesis_note,
                save_video_notes,
                update_moc,
            )

            if not CHANNELS:
                logger.info("No YouTube channels configured — skipping")
                return None

            fetcher = YouTubeFetcher(CHANNELS)
            videos = fetcher.fetch(days=days_back)

            if not videos:
                logger.info("No new YouTube videos found")
                return None

            summary = run_pipeline(videos=videos, use_notebooklm=True, days=days_back)
            save_video_notes(videos, notebook_id=summary.get("notebook_id"))
            save_synthesis_note(videos, summary, days=days_back)
            update_moc(videos)

            return {
                "video_count": len(videos),
                "artifacts": len(summary.get("artifacts", [])),
            }

        result = await asyncio.to_thread(_run)
        if result:
            logger.info(
                "YouTube research complete: %d videos, %d artifacts",
                result["video_count"],
                result["artifacts"],
            )
        else:
            logger.info("YouTube research: nothing to process")
    except Exception as exc:
        logger.exception("YouTube research failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("YouTube Research")
            except ImportError:
                pass


async def research_papers_job():
    """Fetch academic papers and generate NotebookLM digest (non-fatal, config-gated).

    Runs weekly (Saturday morning). Calls AIfirst's research_papers agent via sys.path.
    """
    logger.info("Research papers job started")

    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.research_papers.enabled", False):
            logger.info("Research papers not enabled — skipping")
            return

        days_back = config.get("intelligence.notebooklm.research_papers.days_back", 7)

        def _run():
            aifirst_root = str(Path(__file__).resolve().parents[4] / "AIfirst")
            if aifirst_root not in sys.path:
                sys.path.insert(0, aifirst_root)

            # Also ensure shared_lib is importable
            projects_root = str(Path(__file__).resolve().parents[4])
            if projects_root not in sys.path:
                sys.path.insert(0, projects_root)

            from agents.research_papers.config import TOPICS
            from agents.research_papers.fetcher import (
                SemanticScholarClient,
                score_papers,
            )
            from agents.research_papers.main import (
                run_pipeline,
                save_paper_notes,
                save_synthesis_note,
                update_moc,
            )

            if not TOPICS:
                logger.info("No research topics configured — skipping")
                return None

            client = SemanticScholarClient()
            try:
                papers = client.search(topics=TOPICS, days=days_back)
            finally:
                client.close()

            if not papers:
                logger.info("No new research papers found")
                return None

            # Score papers (graceful fallback if LLM unavailable)
            papers = score_papers(papers)
            if not papers:
                logger.info("No papers passed relevance threshold")
                return None

            summary = run_pipeline(papers=papers, use_notebooklm=True, days=days_back)
            save_paper_notes(papers, notebook_id=summary.get("notebook_id"))
            save_synthesis_note(papers, summary, days=days_back)
            update_moc(papers)

            return {
                "paper_count": len(papers),
                "artifacts": len(summary.get("artifacts", [])),
            }

        result = await asyncio.to_thread(_run)
        if result:
            logger.info(
                "Research papers complete: %d papers, %d artifacts",
                result["paper_count"],
                result["artifacts"],
            )
        else:
            logger.info("Research papers: nothing to process")
    except Exception as exc:
        logger.exception("Research papers failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("Research Papers")
            except ImportError:
                pass


async def notebooklm_keepalive_job():
    """Touch NotebookLM session to delay auth expiry (non-fatal, config-gated).

    Runs daily. Calls shared_lib.notebooklm_utils.check_auth() to verify
    the browser session is still valid. Sends Telegram alert on failure.
    """
    logger.info("NotebookLM keep-alive job started")

    try:
        from regkb.config import config

        if not config.get("intelligence.notebooklm.keepalive.enabled", False):
            logger.info("NotebookLM keep-alive not enabled — skipping")
            return

        def _run():
            shared_lib_parent = str(Path(__file__).resolve().parents[4])
            if shared_lib_parent not in sys.path:
                sys.path.insert(0, shared_lib_parent)

            from shared_lib.notebooklm_utils import check_auth

            return check_auth()

        result = await asyncio.to_thread(_run)

        if result:
            logger.info("NotebookLM session alive — keep-alive successful")
        else:
            logger.warning("NotebookLM session expired — sending alert")
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("Keep-Alive Check")
            except ImportError:
                pass
    except Exception as exc:
        logger.exception("NotebookLM keep-alive failed (non-fatal)")
        if _is_auth_failure(exc):
            try:
                from regkb.telegram.notifications import notify_notebooklm_auth_failure

                await notify_notebooklm_auth_failure("Keep-Alive Check")
            except ImportError:
                pass
