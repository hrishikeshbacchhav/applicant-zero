$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "refresh_company_boards.ps1"
$taskName = "Applicant Zero Daily Refresh"
$taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`""

schtasks.exe /Create /TN $taskName /TR $taskCommand /SC DAILY /ST 08:00 /F
Write-Host "Daily refresh created for 8:00 AM. It runs while this computer is on and you are signed in."
