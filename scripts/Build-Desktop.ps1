param(
    [string]$PythonExe = '',
    [string]$OutputDirectory = '',
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'
$projectDir = Split-Path -Parent $PSScriptRoot
$frontendDir = Join-Path $projectDir 'frontend'
$desktopDir = Join-Path $projectDir 'desktop'

if (-not $PythonExe) {
    $venvPython = Join-Path $projectDir '.venv\Scripts\python.exe'
    if (Test-Path -LiteralPath $venvPython) {
        $PythonExe = $venvPython
    } else {
        $launcher = Get-Command py -ErrorAction SilentlyContinue
        if (-not $launcher) {
            throw 'Python 3.12 is required. Install it or pass -PythonExe with a Python 3.12 executable.'
        }
        & $launcher.Source -3.12 -m venv (Join-Path $projectDir '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Failed to create .venv with Python 3.12.' }
        $PythonExe = $venvPython
    }
}

$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
$pythonVersion = & $PythonExe -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
if ($LASTEXITCODE -ne 0 -or $pythonVersion.Trim() -ne '3.12') {
    throw "Python 3.12 is required for the pinned backend build; selected interpreter is $pythonVersion."
}
Write-Host "Using Python $pythonVersion"

if (-not $OutputDirectory) {
    $OutputDirectory = Join-Path $desktopDir 'dist'
} elseif (-not [System.IO.Path]::IsPathRooted($OutputDirectory)) {
    $OutputDirectory = Join-Path $projectDir $OutputDirectory
}
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)
$appDirectory = Join-Path $OutputDirectory 'ItemTrackingSystem'
if (Test-Path -LiteralPath $appDirectory) {
    throw "Output already exists: $appDirectory. Move or remove that generated package before rebuilding."
}

if (-not $SkipInstall) {
    & $PythonExe -m pip install -r (Join-Path $projectDir 'backend\requirements-lock.txt') `
        -r (Join-Path $desktopDir 'requirements-build.txt')
    if ($LASTEXITCODE -ne 0) { throw 'Failed to install Python build dependencies.' }
}

Push-Location $frontendDir
try {
    if (-not $SkipInstall) {
        npm ci
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed.' }
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'React production build failed.' }
} finally {
    Pop-Location
}

$stageDirectory = Join-Path $desktopDir ("build\package-" + [guid]::NewGuid().ToString('N'))
$backendDistribution = Join-Path $stageDirectory 'backend'
$maintenanceDistribution = Join-Path $stageDirectory 'maintenance'
$desktopDistribution = Join-Path $stageDirectory 'desktop'
$workDirectory = Join-Path $stageDirectory 'work'
New-Item -ItemType Directory -Force -Path $backendDistribution, $maintenanceDistribution, $desktopDistribution, $workDirectory | Out-Null

function Invoke-PyInstaller {
    param([string[]]$Arguments)
    & $PythonExe -m PyInstaller @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller failed: $($Arguments -join ' ')"
    }
}

$pythonEnvironment = Split-Path -Parent $PythonExe
$runtimeDllDirectory = Join-Path $pythonEnvironment 'Library\bin'
$runtimeDllNames = @(
    'ffi.dll',
    'libexpat.dll',
    'liblzma.dll',
    'libbz2.dll',
    'sqlite3.dll',
    'libssl-3-x64.dll',
    'libcrypto-3-x64.dll'
)
$runtimeBinaries = @()
foreach ($dllName in $runtimeDllNames) {
    $dllPath = Join-Path $runtimeDllDirectory $dllName
    if (-not (Test-Path -LiteralPath $dllPath)) {
        throw "Required Anaconda runtime DLL was not found: $dllPath"
    }
    $runtimeBinaries += @('--add-binary', "$dllPath;.")
}

$common = @('--noconfirm', '--clean', '--onedir', '--console') + $runtimeBinaries
$backendWork = Join-Path $workDirectory 'backend'
Invoke-PyInstaller ($common + @(
    '--name', 'ItemTrackingBackend',
    '--distpath', $backendDistribution,
    '--workpath', $backendWork,
    '--specpath', (Join-Path $stageDirectory 'spec-backend'),
    '--paths', (Join-Path $projectDir 'backend'),
    '--collect-all', 'cv2',
    '--collect-all', 'numpy',
    (Join-Path $projectDir 'backend\run.py')
))

$maintenanceWork = Join-Path $workDirectory 'maintenance'
Invoke-PyInstaller ($common + @(
    '--name', 'ItemTrackingMaintenance',
    '--distpath', $maintenanceDistribution,
    '--workpath', $maintenanceWork,
    '--specpath', (Join-Path $stageDirectory 'spec-maintenance'),
    '--paths', (Join-Path $projectDir 'backend'),
    '--collect-all', 'cv2',
    '--collect-all', 'numpy',
    (Join-Path $projectDir 'backend\manage.py')
))

$desktopWork = Join-Path $workDirectory 'desktop'
Invoke-PyInstaller (@(
    '--noconfirm', '--clean', '--onedir', '--windowed',
    '--name', 'ItemTrackingSystem',
    '--distpath', $desktopDistribution,
    '--workpath', $desktopWork,
    '--specpath', (Join-Path $stageDirectory 'spec-desktop'),
    '--paths', $projectDir,
    '--collect-all', 'webview',
    '--collect-all', 'pythonnet',
    '--collect-all', 'clr_loader',
    '--hidden-import', 'clr',
    '--hidden-import', 'webview.platforms.edgechromium',
    '--hidden-import', 'webview.platforms.winforms',
    (Join-Path $projectDir 'desktop\app.py')
) + $runtimeBinaries)

$packageDirectory = Join-Path $desktopDistribution 'ItemTrackingSystem'
$runtimeDirectory = Join-Path $packageDirectory 'runtime'
New-Item -ItemType Directory -Force -Path $runtimeDirectory | Out-Null
Copy-Item -LiteralPath (Join-Path $backendDistribution 'ItemTrackingBackend') `
    -Destination $runtimeDirectory -Recurse
Copy-Item -LiteralPath (Join-Path $maintenanceDistribution 'ItemTrackingMaintenance') `
    -Destination $runtimeDirectory -Recurse
Copy-Item -LiteralPath (Join-Path $frontendDir 'build') `
    -Destination (Join-Path $packageDirectory 'frontend') -Recurse
Copy-Item -LiteralPath (Join-Path $desktopDir 'README.md') `
    -Destination (Join-Path $packageDirectory '使用说明.md')

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Move-Item -LiteralPath $packageDirectory -Destination $appDirectory
Remove-Item -LiteralPath $stageDirectory -Recurse -Force

Write-Host ''
Write-Host 'Desktop package created:' -ForegroundColor Green
Write-Host (Join-Path $appDirectory 'ItemTrackingSystem.exe')
Write-Host 'Copy the complete ItemTrackingSystem directory to the target Windows computer.'
Write-Host 'Microsoft Edge WebView2 Runtime must be installed on the target computer.'
