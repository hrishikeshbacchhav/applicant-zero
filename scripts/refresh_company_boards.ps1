$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$logDirectory = Join-Path $projectRoot "data\logs"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = Join-Path $logDirectory "refresh_$timestamp.log"

New-Item -ItemType Directory -Force $logDirectory | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot "src"

"Applicant Zero refresh started: $(Get-Date)" | Tee-Object -FilePath $logFile
python -m applicant_zero --company-boards (Join-Path $projectRoot "data\company_boards.starter.json") 2>&1 |
    Tee-Object -FilePath $logFile -Append
"Applicant Zero refresh finished: $(Get-Date)" | Tee-Object -FilePath $logFile -Append
