$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
foreach ($port in @(3600, 6060)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        throw "Port $port is already in use. No existing process was stopped."
    }
}
if (!(Test-Path '.venv/Scripts/python.exe') -or !(Test-Path 'frontend/node_modules')) {
    throw 'Run uv sync --locked and npm ci --prefix frontend first.'
}
$taskRoot = (Get-Location).Path
$taskPython = Join-Path $taskRoot '.venv/Scripts/python.exe'
$apiProcess = $null
$workerProcess = $null
try {
    $apiProcess = Start-Process -FilePath $taskPython -ArgumentList @('-m','uvicorn','backend.app:app','--host','127.0.0.1','--port','6060') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data-api.log' -RedirectStandardError 'data-api-error.log'
    $workerProcess = Start-Process -FilePath $taskPython -ArgumentList @('-m','backend.worker') -WorkingDirectory $taskRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput 'data-worker.log' -RedirectStandardError 'data-worker-error.log'
    Write-Host 'DubiSub: http://127.0.0.1:3600 | API: http://127.0.0.1:6060/docs'
    Write-Host 'Keep this terminal open. Ctrl+C stops only these DubiSub processes.'
    npm --prefix frontend run dev
} finally {
    if ($null -ne $workerProcess) { Stop-Process -Id $workerProcess.Id -ErrorAction SilentlyContinue }
    if ($null -ne $apiProcess) { Stop-Process -Id $apiProcess.Id -ErrorAction SilentlyContinue }
}
