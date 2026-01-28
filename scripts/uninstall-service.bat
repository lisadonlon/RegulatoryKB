@echo off
:: RegKB Web Service Uninstaller
:: Run this script as Administrator

echo Uninstalling RegKB Web Service...

:: Check for admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires Administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

set SERVICE_NAME=RegKBWeb

:: Stop and remove service
echo Stopping service...
nssm stop %SERVICE_NAME%

echo Removing service...
nssm remove %SERVICE_NAME% confirm

echo.
echo Service removed.
pause
