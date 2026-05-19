$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"
$LocalDevConfig = Join-Path $Root "runtime\dev.local.ps1"
if (Test-Path $LocalDevConfig) {
    . $LocalDevConfig
}
$CondaEnv = if ($env:Y_CHAT_CONDA_ENV) { $env:Y_CHAT_CONDA_ENV } else { "y_chat" }

Push-Location $BackendDir
try {
    conda run -n $CondaEnv python -c "from y_chat.main import app; from y_chat.events import make_event; print(app.title); print(make_event('system.health','check').model_dump())"
}
finally {
    Pop-Location
}
