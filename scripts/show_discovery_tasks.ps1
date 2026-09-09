$ErrorActionPreference = "Stop"

$tasks = schtasks.exe /Query /FO CSV /NH | ConvertFrom-Csv | Where-Object { $_.TaskName -like "*Applicant Zero Discovery*" }
if (-not $tasks) {
    Write-Host "No Applicant Zero discovery tasks are currently scheduled."
    exit 0
}

$tasks | Select-Object TaskName, Status, 'Next Run Time', 'Last Run Time', 'Last Result' | Format-Table -AutoSize
