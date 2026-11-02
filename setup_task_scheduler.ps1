# PowerShell script to register the AI & Tech Intelligence Brief in Windows Task Scheduler
# Primary automation runs 24/7 on GitHub Actions cloud infrastructure independently of this PC.
# This local scheduled task serves as an automatic secondary backup runner with built-in deduplication.

$TaskName = "AITechIntelligenceBrief"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ActionPath = Join-Path $ScriptDir "run_agent.bat"
$TriggerTime = "07:00AM"

Write-Host "======================================================================"
Write-Host "Registering Windows Scheduled Task: $TaskName..."
Write-Host "  Script: $ActionPath"
Write-Host "  Trigger: Daily at $TriggerTime (Asia/Karachi)"
Write-Host "  Role: Secondary Backup (Primary runs in cloud on GitHub Actions)"
Write-Host "======================================================================"

$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "Removing existing task registration..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

$Action = New-ScheduledTaskAction -Execute $ActionPath -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Daily -At $TriggerTime
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Description "Daily AI & Tech Intelligence Brief (Local Secondary Backup with automated catch-up & deduplication)"

Write-Host "Task '$TaskName' registered successfully!"
Write-Host "Status:"
Get-ScheduledTask -TaskName $TaskName | Select-Object TaskName, State
