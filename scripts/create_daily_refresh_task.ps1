param(
    [string[]]$Times = @("08:00", "13:00", "18:00"),
    [ValidateRange(-1, 14)]
    [int]$MaxQueries = -1,
    [switch]$SyncGmail
)

$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "refresh_company_boards.ps1"
foreach ($time in $Times) {
    if ($time -notmatch "^(?:[01]\d|2[0-3]):[0-5]\d$") {
        throw "Use 24-hour times such as 08:00 or 18:00."
    }
    $taskName = "Applicant Zero Discovery " + $time.Replace(":", "-")
    $gmailArgument = if ($SyncGmail) { " -SyncGmail" } else { "" }
    $taskCommand = "powershell.exe -NoProfile -ExecutionPolicy Bypass -File `"$scriptPath`" -MaxQueries $MaxQueries$gmailArgument"
    schtasks.exe /Create /TN $taskName /TR $taskCommand /SC DAILY /ST $time /F | Out-Null
    Write-Host "Created $taskName."
}
Write-Host "Applicant Zero will refresh while this computer is on and you are signed in. With the default -1 setting, it automatically uses the controlled 14-query broad-feed slice only when real local Adzuna credentials are present; otherwise it remains board-only. Use -MaxQueries 0 to force board-only or a lower positive value to reduce broad-feed calls. Gmail sync runs only when you opt in and a private read-only connection already exists."
