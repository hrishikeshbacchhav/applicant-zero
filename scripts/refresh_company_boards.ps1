$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$stateRoot = if ($env:APPLICANT_ZERO_STATE_DIR) { $env:APPLICANT_ZERO_STATE_DIR } else { Join-Path $env:LOCALAPPDATA "Applicant Zero" }
$logDirectory = Join-Path $stateRoot "logs"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = Join-Path $logDirectory "refresh_$timestamp.log"

New-Item -ItemType Directory -Force $logDirectory | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot "src"

"Applicant Zero daily refresh started: $(Get-Date)" | Tee-Object -FilePath $logFile
python -m applicant_zero --daily-refresh 2>&1 |
    Tee-Object -FilePath $logFile -Append
python -m applicant_zero --daily-digest 2>&1 |
    Tee-Object -FilePath $logFile -Append
"Applicant Zero daily refresh finished: $(Get-Date)" | Tee-Object -FilePath $logFile -Append
Write-Host "Refresh log saved privately: $logFile"
