# PowerShell script to register the AI & Tech Intelligence Brief in Windows Task Scheduler
# Run this once to ensure daily autonomous execution at 07:00 AM even when terminals are closed.

$TaskName = "AITechIntelligenceBrief"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ActionPath = Join-Path $ScriptDir "run_agent.bat"
$TriggerTime = "07:00AM"

Write-Host "Registering Windows Scheduled Task: $TaskName..."
Write-Host "  Script: $ActionPath"
Write-Host "  Trigger: Daily at $TriggerTime"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task registration..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction -Execute $ActionPath -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily 24-hour sweep of AI & Tech landscape, PDF generation, and email to muhammadtalhapro1@gmail.com"

Write-Host "Task '$TaskName' registered successfully!"
Write-Host "Status:"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
