$ErrorActionPreference = "Stop"

$tasks = schtasks.exe /Query /FO CSV /NH | ConvertFrom-Csv | Where-Object { $_.TaskName -like "*Applicant Zero Discovery*" }
foreach ($task in $tasks) {
    schtasks.exe /Delete /TN $task.TaskName /F | Out-Null
    Write-Host "Removed $($task.TaskName)."
}
if (-not $tasks) {
    Write-Host "No Applicant Zero discovery tasks were scheduled."
}
