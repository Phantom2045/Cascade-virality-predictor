$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RootDir "backend"
$FrontendDir = Join-Path $RootDir "frontend"

$VenvPython = Join-Path $BackendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "Virtual environment not found at $VenvPython. Using system python." -ForegroundColor Yellow
    $VenvPython = "python"
}

Write-Host "Starting FastAPI backend on http://127.0.0.1:8000 ..." -ForegroundColor Cyan
$ApiProc = Start-Process -FilePath $VenvPython `
    -ArgumentList "-m", "uvicorn", "app.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
    -WorkingDirectory $BackendDir `
    -PassThru

Write-Host "Starting Vite frontend on http://localhost:5173 ..." -ForegroundColor Cyan
$WebProc = Start-Process -FilePath "npm.cmd" `
    -ArgumentList "run", "dev" `
    -WorkingDirectory $FrontendDir `
    -PassThru

try {
    Write-Host "Both servers running. Press Ctrl+C to stop." -ForegroundColor Green
    while (-not $ApiProc.HasExited -and -not $WebProc.HasExited) {
        Start-Sleep -Seconds 1
    }
}
finally {
    if ($ApiProc -and -not $ApiProc.HasExited) { Stop-Process -Id $ApiProc.Id -Force }
    if ($WebProc -and -not $WebProc.HasExited) { Stop-Process -Id $WebProc.Id -Force }
}
