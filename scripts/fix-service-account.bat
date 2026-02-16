@echo off
:: Fix RegKB service to run as current user
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

echo.
echo Configuring service to run as your user account...
echo You will be prompted for your Windows password.
echo.

nssm set %SERVICE_NAME% ObjectName ".\%USERNAME%"

echo.
echo Starting service...
nssm start %SERVICE_NAME%

timeout /t 3 >nul
nssm status %SERVICE_NAME%

echo.
echo Done! Try http://127.0.0.1:8000
pause
