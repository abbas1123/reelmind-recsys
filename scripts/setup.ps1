# One-time setup: dependencies, data, embedding model, preprocessing, training, database.
# Usage (from the project root):  powershell -ExecutionPolicy Bypass -File scripts\setup.ps1 [-Quick] [-Gpu] [-Posters]
param(
    [switch]$Quick,   # smoke-test training (one configuration per model, ~5 min)
    [switch]$Gpu,     # install the CUDA 12.8 build of torch instead of the CPU build
    [switch]$Posters  # also cache Wikipedia posters (rate-limited by Wikimedia: can take hours; resumable)
)
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
# $ErrorActionPreference does not stop on a failing native command (uv, npm): check the exit code explicitly.
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)." } }

foreach ($tool in "uv", "node", "npm") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) {
        throw "'$tool' was not found on PATH. See README.md (Requirements)."
    }
}

Push-Location (Join-Path $root "backend")
try {
    Step "Installing Python dependencies (uv)"
    if ($Gpu) { uv sync --extra gpu } else { uv sync --extra embeddings }
    Check "uv sync"

    Step "Running the data + training pipeline"
    $pipelineArgs = @("run", "recsys", "pipeline")
    if ($Quick) { $pipelineArgs += "--quick" }
    if ($Posters) { $pipelineArgs += "--posters" }
    & uv @pipelineArgs
    Check "recsys pipeline"

    Step "Verifying saved models"
    uv run recsys evaluate
    Check "recsys evaluate"
}
finally { Pop-Location }

Push-Location (Join-Path $root "frontend")
try {
    Step "Installing frontend dependencies (npm)"
    npm install
    Check "npm install"
}
finally { Pop-Location }

Write-Host "`nDone. Start the app with:  powershell -File scripts\dev.ps1" -ForegroundColor Green
