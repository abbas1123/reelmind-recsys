# Start the FastAPI backend (port 8010) and the Vite frontend (port 5173) together.
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File scripts\dev.ps1
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

$backend = Start-Process -PassThru -NoNewWindow -FilePath "uv" `
    -ArgumentList "run", "recsys", "serve", "--port", "8010" `
    -WorkingDirectory (Join-Path $root "backend")

try {
    Write-Host "Backend:  http://127.0.0.1:8010/docs" -ForegroundColor Cyan
    Write-Host "Frontend: http://127.0.0.1:5173" -ForegroundColor Cyan
    Push-Location (Join-Path $root "frontend")
    npm run dev
}
finally {
    Pop-Location
    if ($backend -and -not $backend.HasExited) {
        Write-Host "Stopping backend (pid $($backend.Id))"
        Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
        # uv starts the server as a child process; stop anything still listening on 8010.
        Get-NetTCPConnection -LocalPort 8010 -State Listen -ErrorAction SilentlyContinue |
            ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
    }
}
