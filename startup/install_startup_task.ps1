# =============================================================================
# install_startup_task.ps1 — Registers the SOAP server as a Windows Task
# SRG Business Services LLC
# =============================================================================
# Run this ONCE as Administrator to make the sync server start automatically
# every time the computer boots.
#
# How to run:
#   1. Right-click PowerShell → "Run as Administrator"
#   2. Navigate to this folder
#   3. Run: .\install_startup_task.ps1
# =============================================================================

$TaskName    = "Crunchtime Sync Server"
$ScriptPath  = Split-Path -Parent $MyInvocation.MyCommand.Path
$BatchFile   = Join-Path $ScriptPath "start_sync_server.bat"

Write-Host ""
Write-Host "Installing Windows Scheduled Task: '$TaskName'" -ForegroundColor Cyan
Write-Host "Batch file: $BatchFile"
Write-Host ""

# Remove existing task if it exists
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
    Write-Host "Removing existing task..." -ForegroundColor Yellow
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Create the action — run the batch file in a minimized window
$Action  = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument "/c `"$BatchFile`"" `
    -WorkingDirectory (Split-Path $BatchFile -Parent)

# Trigger — run at system startup, with a 30-second delay
# (delay gives Windows time to finish booting before the server starts)
$Trigger = New-ScheduledTaskTrigger -AtStartup
$Trigger.Delay = "PT30S"   # 30-second delay after startup

# Settings — run whether or not user is logged in, restart on failure
$Settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable

# Run as SYSTEM so it works even when no one is logged in
$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -LogonType ServiceAccount `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $Action `
    -Trigger   $Trigger `
    -Settings  $Settings `
    -Principal $Principal `
    -Force | Out-Null

Write-Host "Task installed successfully!" -ForegroundColor Green
Write-Host ""
Write-Host "The Crunchtime sync server will now start automatically on every boot."
Write-Host "To test it now: Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "To remove it:   Unregister-ScheduledTask -TaskName '$TaskName'"
Write-Host ""
