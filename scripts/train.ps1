param(
    [Parameter(Mandatory = $false)]
    [string]$Dataset = "twitter15",
    [Parameter(Mandatory = $false)]
    [double]$WindowSeconds = 3600,
    [Parameter(Mandatory = $false)]
    [double]$Quantile = 0.80
)

$ErrorActionPreference = "Stop"
$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    $VenvPython = "python"
}

Push-Location $BackendDir
try {
    & $VenvPython -m app.ml.train --dataset $Dataset --window $WindowSeconds --quantile $Quantile
}
finally {
    Pop-Location
}
