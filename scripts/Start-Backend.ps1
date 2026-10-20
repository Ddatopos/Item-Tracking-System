# 基于神经网络的物品示踪系统 V1.0
param(
    [switch]$Demo,
    [string]$DataDir = '',
    [string]$Source = '0',
    [string]$DetectorFactory = '',
    [string]$CameraFactory = '',
    [string]$FrontendDir = '',
    [int]$Port = 5000
)
$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$pythonExe = Join-Path $projectDir '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw 'Create .venv and install backend/requirements-lock.txt first. See docs/OPERATIONS.md.'
}
if ($Demo -and $DetectorFactory) { throw 'Choose Demo or DetectorFactory.' }
$backendArgs = @((Join-Path $projectDir 'backend\run.py'), '--port', "$Port", '--start')
if ($DataDir) { $backendArgs += @('--data-dir', $DataDir) }
if ($Demo) {
    $backendArgs += @('--camera', 'mock', '--demo', '--infer')
} else {
    $backendArgs += @('--camera', 'opencv', '--source', $Source)
    if ($DetectorFactory) { $backendArgs += @('--detector-factory', $DetectorFactory, '--infer') }
}
if ($CameraFactory) { $backendArgs += @('--camera-factory', $CameraFactory) }
if ($FrontendDir) { $backendArgs += @('--frontend-dir', $FrontendDir) }
Push-Location -LiteralPath $projectDir
try { & $pythonExe @backendArgs; $resultCode = $LASTEXITCODE }
finally { Pop-Location }
exit $resultCode
