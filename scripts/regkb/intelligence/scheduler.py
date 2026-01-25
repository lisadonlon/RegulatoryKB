"""
Scheduled execution support for regulatory intelligence.

Provides utilities for running the intelligence workflow on a schedule,
compatible with Windows Task Scheduler and cron.
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..config import config

logger = logging.getLogger(__name__)

# State file for tracking last run
STATE_FILE = "intelligence_state.json"


class SchedulerState:
    """Tracks state between scheduled runs."""

    def __init__(self) -> None:
        """Initialize the scheduler state."""
        self.state_path = config.base_dir / "db" / STATE_FILE
        self._state = self._load_state()

    def _load_state(self) -> dict:
        """Load state from file."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {
            "last_weekly_run": None,
            "last_daily_run": None,
            "last_monthly_run": None,
            "last_imap_poll": None,
            "entries_seen": [],
        }

    def _save_state(self) -> None:
        """Save state to file."""
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(self._state, f, indent=2)

    @property
    def last_weekly_run(self) -> Optional[datetime]:
        """Get timestamp of last weekly run."""
        ts = self._state.get("last_weekly_run")
        return datetime.fromisoformat(ts) if ts else None

    @property
    def last_daily_run(self) -> Optional[datetime]:
        """Get timestamp of last daily run."""
        ts = self._state.get("last_daily_run")
        return datetime.fromisoformat(ts) if ts else None

    @property
    def last_monthly_run(self) -> Optional[datetime]:
        """Get timestamp of last monthly run."""
        ts = self._state.get("last_monthly_run")
        return datetime.fromisoformat(ts) if ts else None

    @property
    def last_imap_poll(self) -> Optional[datetime]:
        """Get timestamp of last IMAP poll."""
        ts = self._state.get("last_imap_poll")
        return datetime.fromisoformat(ts) if ts else None

    def mark_weekly_run(self) -> None:
        """Mark that weekly run completed."""
        self._state["last_weekly_run"] = datetime.now().isoformat()
        self._save_state()

    def mark_daily_run(self) -> None:
        """Mark that daily run completed."""
        self._state["last_daily_run"] = datetime.now().isoformat()
        self._save_state()

    def mark_monthly_run(self) -> None:
        """Mark that monthly run completed."""
        self._state["last_monthly_run"] = datetime.now().isoformat()
        self._save_state()

    def mark_imap_poll(self) -> None:
        """Mark that IMAP poll completed."""
        self._state["last_imap_poll"] = datetime.now().isoformat()
        self._save_state()

    def should_run_weekly(self) -> bool:
        """Check if weekly digest should run."""
        if self.last_weekly_run is None:
            return True

        # Check if configured day and time
        now = datetime.now()
        weekly_day = config.get("intelligence.schedule.weekly_day", "monday").lower()
        weekly_time = config.get("intelligence.schedule.weekly_time", "08:00")

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        target_day = days.index(weekly_day) if weekly_day in days else 0

        # Run if: correct day, correct time window, and hasn't run today
        if now.weekday() == target_day:
            hour, minute = map(int, weekly_time.split(":"))
            if now.hour >= hour and self.last_weekly_run.date() < now.date():
                return True

        return False

    def should_run_daily(self) -> bool:
        """Check if daily alerts should run."""
        if not config.get("intelligence.schedule.daily_alerts", True):
            return False

        if self.last_daily_run is None:
            return True

        now = datetime.now()
        daily_time = config.get("intelligence.schedule.daily_alert_time", "09:00")
        hour, minute = map(int, daily_time.split(":"))

        # Run if: correct time window and hasn't run today
        if now.hour >= hour and self.last_daily_run.date() < now.date():
            return True

        return False

    def should_run_monthly(self) -> bool:
        """Check if monthly digest should run."""
        if self.last_monthly_run is None:
            return True

        now = datetime.now()
        monthly_day = config.get("intelligence.schedule.monthly_day", 1)

        # Run if: correct day and hasn't run this month
        if now.day == monthly_day:
            if (self.last_monthly_run.year < now.year or
                self.last_monthly_run.month < now.month):
                return True

        return False

    def should_run_imap_poll(self) -> bool:
        """Check if IMAP poll should run based on configured interval."""
        if self.last_imap_poll is None:
            return True

        poll_interval = config.get("intelligence.reply_processing.poll_interval", 30)
        from datetime import timedelta
        next_poll = self.last_imap_poll + timedelta(minutes=poll_interval)

        return datetime.now() >= next_poll


def generate_windows_task_xml(
    task_name: str = "RegulatoryKB_Intel",
    python_path: Optional[str] = None,
    script_path: Optional[str] = None,
    schedule: str = "weekly",
) -> str:
    """
    Generate Windows Task Scheduler XML for the intelligence workflow.

    Args:
        task_name: Name for the scheduled task.
        python_path: Path to Python executable.
        script_path: Path to the run script.
        schedule: Schedule type (weekly, daily).

    Returns:
        XML string for importing into Task Scheduler.
    """
    python_path = python_path or sys.executable
    script_path = script_path or str(config.base_dir / "scripts" / "run_intel.bat")

    # Schedule trigger based on type
    if schedule == "weekly":
        trigger = """
    <CalendarTrigger>
      <StartBoundary>2026-01-27T08:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
          <Monday />
        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>"""
    else:  # daily
        trigger = """
    <CalendarTrigger>
      <StartBoundary>2026-01-27T09:00:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByDay>
        <DaysInterval>1</DaysInterval>
      </ScheduleByDay>
    </CalendarTrigger>"""

    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>RegulatoryKB Intelligence Agent - {schedule} run</Description>
    <Author>RegulatoryKB</Author>
  </RegistrationInfo>
  <Triggers>
    {trigger}
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <AllowHardTerminate>true</AllowHardTerminate>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <AllowStartOnDemand>true</AllowStartOnDemand>
    <Enabled>true</Enabled>
    <Hidden>false</Hidden>
    <ExecutionTimeLimit>PT1H</ExecutionTimeLimit>
    <Priority>7</Priority>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{script_path}</Command>
      <WorkingDirectory>{config.base_dir}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    return xml


def generate_batch_script(
    script_type: str = "weekly",
    include_email: bool = True,
    export_report: bool = True,
) -> str:
    """
    Generate a Windows batch script for scheduled execution.

    Args:
        script_type: Type of run (weekly, daily, monthly).
        include_email: Whether to send email.
        export_report: Whether to export HTML report.

    Returns:
        Batch script content.
    """
    base_dir = config.base_dir
    reports_dir = base_dir / "reports"

    email_flag = "--email" if include_email else "--no-email"
    export_flag = f'--export "{reports_dir}\\intel_{script_type}_%date:~-4,4%%date:~-7,2%%date:~-10,2%.html"' if export_report else ""

    if script_type == "daily":
        command = f"regkb intel email --type daily"
    elif script_type == "monthly":
        command = f"regkb intel run -d 30 {email_flag} {export_flag}"
    else:  # weekly
        command = f"regkb intel run -d 7 {email_flag} {export_flag}"

    script = f"""@echo off
REM RegulatoryKB Intelligence Agent - {script_type.title()} Run
REM Generated by RegulatoryKB

cd /d "{base_dir}"

REM Activate virtual environment if exists
if exist ".venv\\Scripts\\activate.bat" (
    call .venv\\Scripts\\activate.bat
)

REM Set environment variables (edit these!)
REM set ANTHROPIC_API_KEY=your-api-key
REM set SMTP_USERNAME=your-email@gmail.com
REM set SMTP_PASSWORD=your-app-password

REM Create reports directory
if not exist "reports" mkdir reports

REM Run the intelligence workflow
echo Running {script_type} intelligence workflow...
{command}

REM Log completion
echo %date% %time% - {script_type.title()} run completed >> logs\\intel_scheduler.log

REM Pause if run manually (remove for scheduled task)
pause
"""

    return script


def generate_imap_batch_script(
    poll_interval_minutes: int = 30,
    send_confirmations: bool = True,
) -> str:
    """
    Generate a Windows batch script for IMAP polling.

    Args:
        poll_interval_minutes: Minutes between polls.
        send_confirmations: Whether to send confirmation emails.

    Returns:
        Batch script content.
    """
    base_dir = config.base_dir

    confirm_flag = "" if send_confirmations else "--no-confirm"

    script = f"""@echo off
REM RegulatoryKB Intelligence Agent - IMAP Poll
REM Polls for digest reply emails every {poll_interval_minutes} minutes
REM Generated by RegulatoryKB

cd /d "{base_dir}"

REM Activate virtual environment if exists
if exist ".venv\\Scripts\\activate.bat" (
    call .venv\\Scripts\\activate.bat
)

REM Set environment variables (edit these!)
REM IMAP uses same credentials as SMTP for Gmail
REM set IMAP_USERNAME=your-email@gmail.com
REM set IMAP_PASSWORD=your-app-password
REM (Or use SMTP_USERNAME / SMTP_PASSWORD)

REM Create logs directory
if not exist "logs" mkdir logs

:loop
echo.
echo ========================================
echo IMAP Poll - %date% %time%
echo ========================================

REM Poll for replies
regkb intel poll --once {confirm_flag}

REM Log completion
echo %date% %time% - IMAP poll completed >> logs\\intel_imap.log

REM Wait for next poll interval
echo.
echo Waiting {poll_interval_minutes} minutes until next poll...
echo Press Ctrl+C to stop.
timeout /t {poll_interval_minutes * 60} /nobreak > nul

goto loop
"""

    return script


# Global state instance
scheduler_state = SchedulerState()
