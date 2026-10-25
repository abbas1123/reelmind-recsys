# Live demo link: isolated backend (data/demo.db, port 8011) + production build (port 4173)
# + Cloudflare quick tunnel. Anyone with the printed https://*.trycloudflare.com link can use the
# app while this window stays open; your own profiles in data/app.db are not exposed.
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
# Requires: cloudflared  (winget install --id Cloudflare.cloudflared)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command cloudflared -ErrorAction SilentlyContinue)) {
    throw "cloudflared was not found. Install it with: winget install --id Cloudflare.cloudflared"
}

function Stop-Port($port) {
    Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
        ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }
}

Push-Location (Join-Path $root "frontend")
try {
    Write-Host "==> Building the frontend" -ForegroundColor Cyan
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "frontend build failed (exit code $LASTEXITCODE)" }
}
finally { Pop-Location }

$env:RECSYS_PATHS__DB_PATH = "data/demo.db"
$env:VITE_API_PROXY = "http://127.0.0.1:8011"
try {
    Write-Host "==> Starting demo backend on 8011 (data/demo.db)" -ForegroundColor Cyan
    Start-Process -NoNewWindow -FilePath "uv" -ArgumentList "run", "recsys", "serve", "--port", "8011" `
        -WorkingDirectory (Join-Path $root "backend") | Out-Null
    Write-Host "==> Starting production preview on 4173" -ForegroundColor Cyan
    Start-Process -NoNewWindow -FilePath "npm.cmd" -ArgumentList "run", "preview" `
        -WorkingDirectory (Join-Path $root "frontend") | Out-Null

    $deadline = (Get-Date).AddSeconds(120)
    do {
        Start-Sleep -Seconds 2
        try { $ok = (Invoke-RestMethod http://127.0.0.1:8011/api/health -TimeoutSec 3).status -eq "ok" } catch { $ok = $false }
    } until ($ok -or (Get-Date) -gt $deadline)
    if (-not $ok) { throw "demo backend did not become healthy within 2 minutes" }

    Write-Host "==> Opening the tunnel. Share the https://....trycloudflare.com URL printed below. Ctrl+C stops everything." -ForegroundColor Green
    cloudflared tunnel --no-autoupdate --url http://127.0.0.1:4173
}
finally {
    Write-Host "Stopping demo servers"
    Stop-Port 8011
    Stop-Port 4173
}
