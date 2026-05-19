$ErrorActionPreference = "Stop"

$Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$Ports = @(18080, 5173)
$CurrentPid = $PID

Write-Host "Stopping Y_Chat dev shell..."
Write-Host "Root: $Root"

$processes = @(Get-CimInstance Win32_Process)
$byPid = @{}
foreach ($process in $processes) {
    $byPid[[int]$process.ProcessId] = $process
}

$targetIds = [System.Collections.Generic.HashSet[int]]::new()

foreach ($port in $Ports) {
    $connections = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    foreach ($connection in $connections) {
        if ($connection.OwningProcess -and [int]$connection.OwningProcess -ne $CurrentPid) {
            [void]$targetIds.Add([int]$connection.OwningProcess)
        }
    }
}

foreach ($process in $processes) {
    $commandLine = [string]$process.CommandLine
    if ([string]::IsNullOrWhiteSpace($commandLine)) {
        continue
    }

    $isProjectProcess = $commandLine.Contains($Root)
    $isBackendProcess = $process.Name -eq "python.exe" -and $commandLine -match "(^|\s)run_backend\.py(\s|$)"

    if (($isProjectProcess -or $isBackendProcess) -and [int]$process.ProcessId -ne $CurrentPid) {
        [void]$targetIds.Add([int]$process.ProcessId)
    }
}

function Add-Descendants {
    param(
        [int]$ParentId,
        [System.Collections.Generic.HashSet[int]]$Targets,
        [object[]]$AllProcesses
    )

    foreach ($child in $AllProcesses | Where-Object { [int]$_.ParentProcessId -eq $ParentId }) {
        $childId = [int]$child.ProcessId
        if ($childId -ne $CurrentPid -and $Targets.Add($childId)) {
            Add-Descendants -ParentId $childId -Targets $Targets -AllProcesses $AllProcesses
        }
    }
}

foreach ($id in @($targetIds)) {
    Add-Descendants -ParentId $id -Targets $targetIds -AllProcesses $processes
}

$stopped = 0
foreach ($id in @($targetIds) | Sort-Object -Descending) {
    if ($id -eq $CurrentPid) {
        continue
    }

    try {
        $process = Get-Process -Id $id -ErrorAction Stop
        Write-Host "Stopping PID $id ($($process.ProcessName))"
        Stop-Process -Id $id -Force -ErrorAction Stop
        $stopped += 1
    }
    catch {
        Write-Host "PID $id is already stopped or unavailable."
    }
}

if ($stopped -eq 0) {
    Write-Host "No Y_Chat dev processes found."
}
else {
    Write-Host "Stopped $stopped process(es)."
}
