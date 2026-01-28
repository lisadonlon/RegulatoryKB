@echo off
:: Install ALL project dependencies globally (requires admin)
:: Run as Administrator

net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Run as Administrator
    pause
    exit /b 1
)

echo Installing all dependencies to system Python...
echo This may take a minute...

C:\Python313\python.exe -m pip install --target "C:\Python313\Lib\site-packages" ^
    pyyaml ^
    click ^
    pymupdf ^
    sentence-transformers ^
    chromadb ^
    requests ^
    tqdm ^
    python-dateutil ^
    colorlog ^
    uvicorn ^
    fastapi ^
    jinja2 ^
    python-multipart ^
    itsdangerous ^
    starlette ^
    pydantic

echo.
echo Restarting RegKBWeb service...
nssm restart RegKBWeb

timeout /t 5 >nul
nssm status RegKBWeb

echo.
echo Try http://127.0.0.1:8000
pause
