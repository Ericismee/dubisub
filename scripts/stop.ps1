$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskManifest = Join-Path $taskRoot 'data/launcher.json'
if (!(Test-Path -LiteralPath $taskManifest)) { Write-Host 'No recorded DubiSub launcher.'; exit 0 }
$taskRecord = Get-Content -LiteralPath $taskManifest -Raw | ConvertFrom-Json
if ($taskRecord.root -ne $taskRoot) { throw 'Launcher workspace does not match.' }
$taskProcess = Get-Process -Id $taskRecord.pid -ErrorAction SilentlyContinue
if ($null -eq $taskProcess) { Write-Host 'DubiSub launcher already stopped.'; exit 0 }
if ([string]$taskProcess.StartTime.ToUniversalTime().Ticks -ne [string]$taskRecord.startTicks) {
    throw 'Recorded PID has been reused; refusing to stop another process.'
}
# Stop only the process tree started by this workspace's recorded launcher.
& taskkill.exe /PID ([string]$taskProcess.Id) /T /F
if ($LASTEXITCODE -ne 0) { throw 'Could not stop the DubiSub launcher tree.' }
