@echo off
REM RegulatoryKB Intelligence Agent - Weekly Digest
REM Run this every Monday to generate and send the weekly regulatory digest
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
if not exist "reports" mkdir reports
if not exist "logs" mkdir logs

REM Log start time
echo %date% %time% - Starting weekly intelligence run >> logs\intel_scheduler.log

REM Run the weekly intelligence workflow
REM  -d 7 = look back 7 days
REM  --email = send email digest
REM  --export = save HTML report
python -m regkb intel run -d 7 --email --export "reports\intel_weekly_%date:~-4,4%%date:~-7,2%%date:~-10,2%.html"

REM Log completion
echo %date% %time% - Weekly run completed (exit code: %ERRORLEVEL%) >> logs\intel_scheduler.log

REM If running manually, pause to see output
if "%1"=="" pause
