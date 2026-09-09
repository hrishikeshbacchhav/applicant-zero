param(
    [string[]]$Times = @("08:00", "13:00", "18:00"),
    [ValidateRange(0, 7)]
    [int]$MaxQueries = 0
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "refresh_company_boards.ps1"
foreach ($time in $Times) {
    if ($time -notmatch "^(?:[01]\d|2[0-3]):[0-5]\d$") {
        throw "Use 24-hour times such as 08:00 or 18:00."
    }
    $taskName = "Applicant Zero Discovery " + $time.Replace(":", "-")
    $taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -MaxQueries $MaxQueries"
    schtasks.exe /Create /TN $taskName /TR $taskCommand /SC DAILY /ST $time /F | Out-Null
    Write-Host "Created $taskName."
}
Write-Host "Applicant Zero will refresh while this computer is on and you are signed in. Board-only discovery is enabled by default; MaxQueries stays at 0 unless you choose to use the broad job-feed API."
