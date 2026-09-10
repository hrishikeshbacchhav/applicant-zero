param(
    [ValidateRange(0, 7)]
    [int]$MaxQueries = 0,
    [switch]$SyncGmail
)

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$stateRoot = if ($env:APPLICANT_ZERO_STATE_DIR) { $env:APPLICANT_ZERO_STATE_DIR } else { Join-Path $env:LOCALAPPDATA "Applicant Zero" }
$logDirectory = Join-Path $stateRoot "logs"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$logFile = Join-Path $logDirectory "refresh_$timestamp.log"

New-Item -ItemType Directory -Force $logDirectory | Out-Null
$env:PYTHONPATH = Join-Path $projectRoot "src"

"Applicant Zero discovery refresh started: $(Get-Date)" | Tee-Object -FilePath $logFile
try {
    python -m applicant_zero --daily-refresh --max-queries $MaxQueries 2>&1 |
        Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Applicant Zero discovery returned exit code $LASTEXITCODE."
    }
    python -m applicant_zero --daily-digest 2>&1 |
        Tee-Object -FilePath $logFile -Append
    if ($LASTEXITCODE -ne 0) {
        throw "Applicant Zero daily digest returned exit code $LASTEXITCODE."
    }
    if ($SyncGmail) {
        $gmailToken = Join-Path $stateRoot "private\gmail_token.json"
        if (Test-Path -LiteralPath $gmailToken) {
            "Applicant Zero read-only Gmail sync started: $(Get-Date)" | Tee-Object -FilePath $logFile -Append
            python -m applicant_zero --gmail-sync 2>&1 |
                Tee-Object -FilePath $logFile -Append
            if ($LASTEXITCODE -ne 0) {
                throw "Applicant Zero Gmail sync returned exit code $LASTEXITCODE."
            }
        }
        else {
            "Applicant Zero Gmail sync skipped: no private Gmail connection is present." | Tee-Object -FilePath $logFile -Append
        }
    }
    "Applicant Zero discovery refresh finished successfully: $(Get-Date)" | Tee-Object -FilePath $logFile -Append
    Write-Host "Refresh log saved privately: $logFile"
}
catch {
    "Applicant Zero discovery refresh failed: $($_.Exception.Message)" | Tee-Object -FilePath $logFile -Append
    Write-Error "Discovery refresh failed. Check the private log: $logFile"
    exit 1
}
