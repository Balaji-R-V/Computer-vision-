# Registers Aegis-OS to start at boot and restart itself if it crashes (Windows Task Scheduler).
# Run once from an elevated (Administrator) PowerShell:   .\install_autostart.ps1
# Remove with:                                              .\install_autostart.ps1 -Remove
param([switch]$Remove)

$TaskName = 'Aegis-OS'
if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) { Write-Error 'Run this from an elevated (Administrator) PowerShell.'; exit 1 }

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
New-Item -ItemType Directory -Force -Path (Join-Path $root 'logs') | Out-Null

$action   = New-ScheduledTaskAction -Execute (Join-Path $root 'run_server.bat') -WorkingDirectory $root
$trigger  = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1) `
            -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
# Runs as the current user so it can reach the same Python packages and GPU drivers.
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType S4U -RunLevel Highest

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force | Out-Null
Write-Host "Installed '$TaskName': starts at boot, restarts every minute if it stops. Logs: $root\logs\server.log"
Write-Host "Start it now with:  Start-ScheduledTask -TaskName $TaskName"
