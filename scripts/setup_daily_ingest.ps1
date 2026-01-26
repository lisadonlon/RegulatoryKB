# Setup Daily Ingest Task for RegKB
# Run this script as Administrator to create the scheduled task

$TaskName = "RegKB Daily Ingest"
$Description = "Automatically imports PDFs from the pending folder into the Regulatory Knowledge Base"
$RegKBPath = "C:\Projects\RegulatoryKB"
$ExePath = "$RegKBPath\.venv\Scripts\regkb.exe"

# Check if task already exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Task '$TaskName' already exists. Removing and recreating..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action
$Action = New-ScheduledTaskAction -Execute $ExePath -Argument "ingest" -WorkingDirectory $RegKBPath

# Create the trigger (daily at 7:00 AM)
$Trigger = New-ScheduledTaskTrigger -Daily -At 7:00AM

# Create settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

# Register the task
Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description $Description

Write-Host ""
Write-Host "Scheduled task '$TaskName' created successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "Details:" -ForegroundColor Cyan
Write-Host "  - Runs daily at 7:00 AM"
Write-Host "  - Command: regkb ingest"
Write-Host "  - Working directory: $RegKBPath"
Write-Host ""
Write-Host "To modify the schedule, open Task Scheduler and edit '$TaskName'"
Write-Host "To run manually: regkb ingest"
