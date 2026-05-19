$ErrorActionPreference = "Stop"

$Root = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $Root "backend"

Push-Location $BackendDir
try {
    conda run -n Atri_2 python -c "from test_atri.main import app; from test_atri.events import make_event; print(app.title); print(make_event('system.health','check').model_dump())"
}
finally {
    Pop-Location
}

