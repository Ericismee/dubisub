$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$taskRuntime = Join-Path $taskRoot 'data/vieneu-runtime'
$taskPython = Join-Path $taskRuntime '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $taskPython)) { throw 'Install the pinned isolated VieNeu runtime first.' }
if (Get-NetTCPConnection -LocalPort 8001 -State Listen -ErrorAction SilentlyContinue) { throw 'Port 8001 is occupied; no service was stopped.' }
Set-Location $taskRoot
& $taskPython (Join-Path $PSScriptRoot 'prepare_vieneu_models.py')
if ($LASTEXITCODE -ne 0) { throw 'Could not prepare isolated model files.' }
$env:HF_HOME = Join-Path $taskRuntime 'huggingface'
$env:HF_HUB_DISABLE_IMPLICIT_TOKEN = '1'
$env:VIENEU_BACKEND = 'onnx'
$env:VIENEU_DEVICE = 'cpu'
$env:VIENEU_PRECISION = 'fp32'
$env:VIENEU_MAX_STREAMS = '1'
$env:HOST = '127.0.0.1'
$env:PORT = '8001'
$env:PYTHONUTF8 = '1'
@{pid=$PID;startTicks=[string](Get-Process -Id $PID).StartTime.ToUniversalTime().Ticks;root=$taskRoot} | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $taskRuntime 'launcher.json')
& $taskPython -m apps.openai_speech
if ($LASTEXITCODE -ne 0) { throw 'VieNeu could not start; inspect data/vieneu-runtime/service-error.log' }
