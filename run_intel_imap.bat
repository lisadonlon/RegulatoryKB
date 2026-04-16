@echo off
REM RegulatoryKB Intelligence Agent - IMAP Poll (one-shot)
REM Polls for digest reply emails ONCE and exits.
REM Cadence is provided by Windows Task Scheduler ("RegKB IMAP Poll", every 30 min).
REM
REM NOTE: This file was hand-edited from the looping version that
REM `regkb intel setup --type imap` generates. If you regenerate it,
REM strip the :loop / timeout / goto so it stays a one-shot.

cd /d "%~dp0"

REM Activate virtual environment if exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

REM Create logs directory
if not exist "logs" mkdir logs

echo.
echo ========================================
echo IMAP Poll - %date% %time%
echo ========================================

REM Poll for replies (single pass)
python -m regkb intel poll --once
set POLL_EXIT=%errorlevel%

echo %date% %time% - IMAP poll completed (exit code: %POLL_EXIT%) >> logs\intel_imap.log

exit /b %POLL_EXIT%
