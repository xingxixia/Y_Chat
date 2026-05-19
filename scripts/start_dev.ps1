$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$FrontendDir = Join-Path $Root "frontend"
$LogDir = Join-Path $Root "runtime\logs"
New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

$backendOutLog = Join-Path $LogDir "backend-dev.out.log"
$backendErrLog = Join-Path $LogDir "backend-dev.err.log"
$viteOutLog = Join-Path $LogDir "frontend-vite.out.log"
$viteErrLog = Join-Path $LogDir "frontend-vite.err.log"
$electronOutLog = Join-Path $LogDir "electron.out.log"
$electronErrLog = Join-Path $LogDir "electron.err.log"

Write-Host "Starting test atri dev shell..."
Write-Host "Root: $Root"

$backend = Start-Process -FilePath "conda" `
    -ArgumentList @("run", "-n", "Atri_2", "python", "run_backend.py") `
    -WorkingDirectory $BackendDir `
    -RedirectStandardOutput $backendOutLog `
    -RedirectStandardError $backendErrLog `
    -PassThru `
    -WindowStyle Hidden

Write-Host "Backend PID: $($backend.Id)"
Start-Sleep -Seconds 2

$vite = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $viteOutLog `
    -RedirectStandardError $viteErrLog `
    -PassThru `
    -WindowStyle Hidden

Write-Host "Vite PID: $($vite.Id)"
Start-Sleep -Seconds 3

$electron = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "electron") `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $electronOutLog `
    -RedirectStandardError $electronErrLog `
    -PassThru

Write-Host "Electron PID: $($electron.Id)"
Write-Host "Logs:"
Write-Host "  $backendOutLog"
Write-Host "  $backendErrLog"
Write-Host "  $viteOutLog"
Write-Host "  $viteErrLog"
Write-Host "  $electronOutLog"
Write-Host "  $electronErrLog"
Write-Host "Use Ctrl+Space for the command bubble, Ctrl+Shift+P for debug, Esc to interrupt/hide bubble."
