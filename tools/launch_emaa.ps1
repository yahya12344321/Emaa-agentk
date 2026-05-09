$ErrorActionPreference = "Stop"
if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$projectRoot = Split-Path -Parent $PSScriptRoot
$statusFile = Join-Path $projectRoot ".emaa-launch-status"
$fullUrl = "http://127.0.0.1:8000"
$fullHealthUrl = "$fullUrl/health"
$staticUrl = "http://127.0.0.1:4173"
$startupTimeoutSeconds = 45

function Write-LaunchStatus {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Mode,
        [string]$Url = "",
        [bool]$BackendAvailable = $false,
        [string]$Details = ""
    )

    @(
        "MODE=$Mode"
        "URL=$Url"
        "BACKEND_AVAILABLE=$BackendAvailable"
        "DETAILS=$Details"
    ) | Set-Content -LiteralPath $statusFile -Encoding ASCII
}

function Test-CommandAvailable {
    param(
        [Parameter(Mandatory = $true)]
        [string]$CommandName
    )

    return [bool](Get-Command $CommandName -ErrorAction SilentlyContinue)
}

function Resolve-NodeExecutable {
    $candidates = @()
    $nodeCommand = Get-Command node -ErrorAction SilentlyContinue

    if ($nodeCommand -and $nodeCommand.Source) {
        $candidates += $nodeCommand.Source
    }

    $candidates += @(
        "C:\Users\kk200\AppData\Local\OpenAI\Codex\bin\node.exe",
        "C:\Users\kk200\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe",
        "C:\Program Files\WindowsApps\OpenAI.Codex_26.429.8261.0_x64__2p2nqsd0c76g0\app\resources\node.exe"
    )

    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }

    return $null
}

function Test-FullPythonDeps {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Launcher,
        [string[]]$LauncherArgs = @()
    )

    $dependencyCheck = @(
        "-c",
        "import fastapi, mediapipe, cv2, uvicorn, h5py; import tensorflow as tf; from tensorflow.keras.models import load_model"
    )

    try {
        & $Launcher @LauncherArgs @dependencyCheck *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Test-PythonLauncherWorks {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Launcher,
        [string[]]$LauncherArgs = @()
    )

    try {
        & $Launcher @LauncherArgs -c "import sys" *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Wait-HttpReady {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url,
        [int]$TimeoutSeconds = 45
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing $Url -TimeoutSec 3
            if ($response.StatusCode -ge 200 -and $response.StatusCode -lt 400) {
                return $true
            }
        } catch {
        }

        Start-Sleep -Milliseconds 900
    }

    return $false
}

function Open-Url {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Url
    )

    if ($env:EMAA_NO_BROWSER -eq "1") {
        return
    }

    Start-Process $Url | Out-Null
}

function Start-ServerWindow {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WindowTitle,
        [Parameter(Mandatory = $true)]
        [string]$CommandLine
    )

    $command = "title $WindowTitle && cd /d `"$projectRoot`" && $CommandLine"
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", $command -WorkingDirectory $projectRoot | Out-Null
}

function Launch-FullMode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Launcher,
        [string[]]$LauncherArgs = @()
    )

    $commandLine = if ($LauncherArgs.Count) {
        "$Launcher $($LauncherArgs -join ' ') server.py"
    } else {
        "$Launcher server.py"
    }

    Write-Host "[OK] Starting full EMAA server..." -ForegroundColor Green
    Start-ServerWindow -WindowTitle "EMAA Full Server" -CommandLine $commandLine

    if (Wait-HttpReady -Url $fullHealthUrl -TimeoutSeconds $startupTimeoutSeconds) {
        Write-LaunchStatus -Mode "full" -Url $fullUrl -BackendAvailable $true -Details "Python backend active"
        Open-Url -Url $fullUrl
        Write-Host "[OK] EMAA opened at $fullUrl" -ForegroundColor Green
        return $true
    }

    Write-Warning "The full server did not become ready on $fullUrl."
    return $false
}

function Launch-StaticMode {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ModeName,
        [Parameter(Mandatory = $true)]
        [string]$CommandLine
    )

    Write-Host "[OK] Starting browser-only mode ($ModeName)..." -ForegroundColor Yellow
    Start-ServerWindow -WindowTitle "EMAA Static Server" -CommandLine $CommandLine

    if (Wait-HttpReady -Url $staticUrl -TimeoutSeconds 20) {
        Write-LaunchStatus -Mode "static" -Url $staticUrl -BackendAvailable $false -Details "Browser-only mode without Python backend"
        Open-Url -Url $staticUrl
        Write-Host "[OK] EMAA opened at $staticUrl" -ForegroundColor Green
        Write-Host "[INFO] Word recognition via Python backend will stay unavailable until full dependencies are installed." -ForegroundColor Yellow
        return $true
    }

    Write-Warning "The browser-only server did not become ready on $staticUrl."
    return $false
}

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "EMAA - Sign Language Educational Platform" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "Preparing EMAA..." -ForegroundColor White
Write-Host ""

if (Test-Path -LiteralPath $statusFile) {
    Remove-Item -LiteralPath $statusFile -Force -ErrorAction SilentlyContinue
}

if (Wait-HttpReady -Url $fullHealthUrl -TimeoutSeconds 2) {
    Write-Host "[OK] Full EMAA server is already running." -ForegroundColor Green
    Write-LaunchStatus -Mode "full" -Url $fullUrl -BackendAvailable $true -Details "Full server already running"
    Open-Url -Url $fullUrl
    exit 0
}

if (Wait-HttpReady -Url $staticUrl -TimeoutSeconds 2) {
    Write-Host "[OK] Browser-only EMAA server is already running." -ForegroundColor Green
    Write-LaunchStatus -Mode "static" -Url $staticUrl -BackendAvailable $false -Details "Browser-only server already running"
    Open-Url -Url $staticUrl
    exit 0
}

$pyAvailable = Test-CommandAvailable -CommandName "py"
$pythonAvailable = Test-CommandAvailable -CommandName "python"
$nodeExecutable = Resolve-NodeExecutable
$nodeAvailable = [bool]$nodeExecutable
$pyUsable = $pyAvailable -and (Test-PythonLauncherWorks -Launcher "py" -LauncherArgs @("-3"))
$pythonUsable = $pythonAvailable -and (Test-PythonLauncherWorks -Launcher "python")

if ($pyUsable -and (Test-FullPythonDeps -Launcher "py" -LauncherArgs @("-3"))) {
    if (Launch-FullMode -Launcher "py" -LauncherArgs @("-3")) {
        exit 0
    }
}

if ($pythonUsable -and (Test-FullPythonDeps -Launcher "python")) {
    if (Launch-FullMode -Launcher "python") {
        exit 0
    }
}

if ($nodeAvailable) {
    $quotedNodeExecutable = '"' + $nodeExecutable + '"'
    if (Launch-StaticMode -ModeName "Node.js static server" -CommandLine "$quotedNodeExecutable tools\static_server.js 4173") {
        exit 0
    }
}

if ($pyUsable) {
    if (Launch-StaticMode -ModeName "Python http.server" -CommandLine "py -3 -m http.server 4173 --bind 127.0.0.1") {
        exit 0
    }
}

if ($pythonUsable) {
    if (Launch-StaticMode -ModeName "Python http.server" -CommandLine "python -m http.server 4173 --bind 127.0.0.1") {
        exit 0
    }
}

Write-LaunchStatus -Mode "failed" -BackendAvailable $false -Details "No supported runtime could start EMAA"
Write-Error "No supported runtime could start EMAA. Install Python 3, or Node.js, then try again."
