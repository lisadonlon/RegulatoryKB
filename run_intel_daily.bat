@echo off
REM RegulatoryKB Intelligence Agent - Daily Alerts
REM Run this daily to check for high-priority regulatory updates
REM
REM Setup:
REM   1. Set environment variables below (or in system environment)
REM   2. Import into Task Scheduler or run manually

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM ============================================================================
REM CONFIGURATION - Edit these values
REM ============================================================================
REM Anthropic API key for LLM summaries (required for summaries)
REM set ANTHROPIC_API_KEY=your-api-key-here

REM Email credentials (required for sending emails)
REM set SMTP_USERNAME=your-email@gmail.com
REM set SMTP_PASSWORD=your-app-password

REM ============================================================================
REM EXECUTION
REM ============================================================================

REM Create directories if needed
if not exist "logs" mkdir logs

REM Log start time
echo %date% %time% - Starting daily alert check >> logs\intel_scheduler.log

REM Run daily alert check
REM Only sends email if high-priority items found in last 24 hours
python -m regkb intel email --type daily

REM Log completion
echo %date% %time% - Daily check completed (exit code: %ERRORLEVEL%) >> logs\intel_scheduler.log

REM If running manually, pause to see output
if "%1"=="" pause
