@echo off
echo Starting Regulatory Knowledge Base...
echo.
echo The web interface will open in your browser.
echo Press Ctrl+C in this window to stop the server.
echo.
cd /d "%~dp0"
call .venv\Scripts\activate
streamlit run scripts\regkb\app.py --server.headless=true
pause
