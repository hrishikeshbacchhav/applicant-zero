$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$backupRoot = Join-Path $projectRoot "private\backups"
$timestamp = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"
$backupFolder = Join-Path $backupRoot "applicant-zero_$timestamp"

New-Item -ItemType Directory -Force $backupFolder | Out-Null

$database = Join-Path $projectRoot "data\applicant_zero.sqlite3"
if (Test-Path $database) { Copy-Item -LiteralPath $database -Destination $backupFolder }

foreach ($name in @("candidate_profile.json", "candidate_evidence.json", "application_answers.json")) {
    $source = Join-Path $projectRoot "private\$name"
    if (Test-Path $source) { Copy-Item -LiteralPath $source -Destination $backupFolder }
}

Write-Host "Private backup created: $backupFolder"
Write-Host "This backup contains your local tracker and private configuration. It is not uploaded anywhere."
