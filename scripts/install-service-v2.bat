@echo off
:: RegKB Web Service Installer v2
:: Run this script as Administrator
::
:: Changes from v1:
:: - Uses Python 3.11 (the working installation)
:: - Sets REGKB_BASE_DIR environment variable
:: - Loads .env file for secrets
:: - Single process: FastAPI + APScheduler + Telegram bot

echo ============================================
echo  RegKB Web Service Installer v2
echo ============================================
echo.

:: Check for admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires Administrator privileges.
    echo Right-click and select "Run as administrator"
    pause
    exit /b 1
)

:: Configuration
set SERVICE_NAME=RegKBWeb
set PYTHON_EXE=C:\Python311x64\python.exe
set PROJECT_DIR=C:\Projects\RegulatoryKB
set HOST=127.0.0.1
set PORT=8000

:: Verify Python exists
if not exist "%PYTHON_EXE%" (
    echo ERROR: Python not found at %PYTHON_EXE%
    echo Please update PYTHON_EXE in this script.
    pause
    exit /b 1
)

echo Using Python: %PYTHON_EXE%
echo Project dir:  %PROJECT_DIR%
echo.

:: Stop and remove existing service if present
echo Removing existing service (if any)...
nssm stop %SERVICE_NAME% >nul 2>&1
timeout /t 2 >nul
nssm remove %SERVICE_NAME% confirm >nul 2>&1

:: Create logs directory if needed
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

:: Install service
echo Creating service %SERVICE_NAME%...
nssm install %SERVICE_NAME% "%PYTHON_EXE%" -m uvicorn regkb.web.main:app --host %HOST% --port %PORT%

:: Set working directory
nssm set %SERVICE_NAME% AppDirectory "%PROJECT_DIR%"

:: Set display name and description
nssm set %SERVICE_NAME% DisplayName "RegKB Web Interface"
nssm set %SERVICE_NAME% Description "Regulatory Knowledge Base - FastAPI + Telegram Bot + Scheduler"

:: Set environment variables
:: REGKB_BASE_DIR tells the app where to find config, DB, etc.
:: PYTHONPATH ensures regkb package is importable
nssm set %SERVICE_NAME% AppEnvironmentExtra ^
    REGKB_BASE_DIR=%PROJECT_DIR% ^
    PYTHONPATH=%PROJECT_DIR%\scripts

:: Set startup type to automatic
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

:: Configure stdout/stderr logging
nssm set %SERVICE_NAME% AppStdout "%PROJECT_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%PROJECT_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStdoutCreationDisposition 4
nssm set %SERVICE_NAME% AppStderrCreationDisposition 4
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 1048576

:: Configure restart on crash
nssm set %SERVICE_NAME% AppThrottle 5000
nssm set %SERVICE_NAME% AppExit Default Restart

:: Start the service
echo Starting service...
nssm start %SERVICE_NAME%

:: Wait and check status
timeout /t 3 >nul
nssm status %SERVICE_NAME%

echo.
echo ============================================
echo  Service installed and started!
echo ============================================
echo.
echo Web UI:    http://%HOST%:%PORT%
echo Health:    http://%HOST%:%PORT%/health
echo Logs:      %PROJECT_DIR%\logs\service.log
echo.
echo Management commands:
echo   nssm status RegKBWeb     - Check status
echo   nssm stop RegKBWeb       - Stop service
echo   nssm start RegKBWeb      - Start service
echo   nssm restart RegKBWeb    - Restart service
echo   nssm edit RegKBWeb       - Edit configuration (GUI)
echo.
pause
