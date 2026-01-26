@echo off
echo Creating scheduled task: RegKB Daily Ingest
echo.

schtasks /create /tn "RegKB Daily Ingest" /tr "C:\Projects\RegulatoryKB\.venv\Scripts\regkb.exe ingest" /sc daily /st 07:00 /f

echo.
if %errorlevel%==0 (
    echo Task created successfully! Runs daily at 7:00 AM.
) else (
    echo Failed to create task. Try running as Administrator.
)
echo.
pause
