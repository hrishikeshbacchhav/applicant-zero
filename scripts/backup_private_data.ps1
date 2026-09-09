$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$env:PYTHONPATH = Join-Path $projectRoot "src"
python -m applicant_zero --backup
Write-Host "The snapshot is stored under your private Applicant Zero runtime folder and is not uploaded anywhere."
