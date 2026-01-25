# Regulatory Knowledge Base - Web UI Launcher
Write-Host "Starting Regulatory Knowledge Base..." -ForegroundColor Green
Write-Host ""
Write-Host "The web interface will open in your browser."
Write-Host "Press Ctrl+C to stop the server."
Write-Host ""

Set-Location $PSScriptRoot
& .\.venv\Scripts\Activate.ps1
streamlit run scripts\regkb\app.py --server.headless=true
