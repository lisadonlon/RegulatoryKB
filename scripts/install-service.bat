@echo off
:: RegKB Web Service Installer
:: Run this script as Administrator

echo Installing RegKB Web Service...

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
set PYTHON_EXE=C:\Python313\python.exe
set PROJECT_DIR=C:\Projects\RegulatoryKB
set HOST=127.0.0.1
set PORT=8000

:: Remove existing service if present
nssm stop %SERVICE_NAME% >nul 2>&1
nssm remove %SERVICE_NAME% confirm >nul 2>&1

:: Install service
echo Creating service %SERVICE_NAME%...
nssm install %SERVICE_NAME% "%PYTHON_EXE%" -m uvicorn regkb.web.main:app --host %HOST% --port %PORT%

:: Set working directory
nssm set %SERVICE_NAME% AppDirectory "%PROJECT_DIR%"

:: Set display name and description
nssm set %SERVICE_NAME% DisplayName "RegKB Web Interface"
nssm set %SERVICE_NAME% Description "Regulatory Knowledge Base - FastAPI Web UI"

:: Set startup type to automatic
nssm set %SERVICE_NAME% Start SERVICE_AUTO_START

:: Configure stdout/stderr logging
nssm set %SERVICE_NAME% AppStdout "%PROJECT_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStderr "%PROJECT_DIR%\logs\service.log"
nssm set %SERVICE_NAME% AppStdoutCreationDisposition 4
nssm set %SERVICE_NAME% AppStderrCreationDisposition 4
nssm set %SERVICE_NAME% AppRotateFiles 1
nssm set %SERVICE_NAME% AppRotateBytes 1048576

:: Create logs directory if needed
if not exist "%PROJECT_DIR%\logs" mkdir "%PROJECT_DIR%\logs"

:: Start the service
echo Starting service...
nssm start %SERVICE_NAME%

:: Check status
timeout /t 2 >nul
nssm status %SERVICE_NAME%

echo.
echo Service installed and started!
echo Web UI available at: http://%HOST%:%PORT%
echo.
echo Management commands:
echo   nssm status RegKBWeb     - Check status
echo   nssm stop RegKBWeb       - Stop service
echo   nssm start RegKBWeb      - Start service
echo   nssm restart RegKBWeb    - Restart service
echo   nssm edit RegKBWeb       - Edit configuration (GUI)
echo.
pause
