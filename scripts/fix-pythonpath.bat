@echo off
:: Fix PYTHONPATH for RegKB service
:: Run as Administrator

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run as Administrator
    pause
    exit /b 1
)

set SERVICE_NAME=RegKBWeb

echo Stopping service...
nssm stop %SERVICE_NAME%

echo Setting PYTHONPATH...
nssm set %SERVICE_NAME% AppEnvironmentExtra PYTHONPATH=C:\Projects\RegulatoryKB\scripts

echo Starting service...
nssm start %SERVICE_NAME%

timeout /t 3 >nul
nssm status %SERVICE_NAME%

echo.
echo Try http://127.0.0.1:8000
pause
