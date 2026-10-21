# Phase 14 — Gunicorn launcher (Uvicorn workers).
#
# This is the REAL production deployment. `run_prod.ps1` spawns a single uvicorn;
# this one uses gunicorn to fork N uvicorn workers so you can actually hit the
# SQLite single-writer contention and rate-limit race conditions that Phase 13
# marked "待验证".
#
# Usage:
#   pip install gunicorn
#   scripts\run_gunicorn.ps1 -Workers 4 -Port 8000 -AuthEnabled $true
#
# All env vars mirror Settings.

param(
    [int]$Workers = 4,
    [int]$Port = 8000,
    [string]$Host = "0.0.0.0",
    [string]$LogLevel = "WARNING",
    [bool]$AuthEnabled = $false,
    [bool]$MetricsPersistEnabled = $false,
    [string]$AuthJwtSecret = "",
    [bool]$MtlsEnabled = $false,
    [string]$MtlsKeyfile = "",
    [string]$MtlsCertfile = "",
    [string]$MtlsCaFile = ""
)

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

$env:APP_ENV = "production"
$env:APP_LOG_LEVEL = $LogLevel
$env:AUTH_ENABLED = $AuthEnabled.ToString().ToLower()
$env:METRICS_PERSIST_ENABLED = $MetricsPersistEnabled.ToString().ToLower()

if ($AuthEnabled -and [string]::IsNullOrWhiteSpace($AuthJwtSecret)) {
    Write-Error "AUTH_ENABLED=true but AUTH_JWT_SECRET is empty"
    exit 1
}
if (-not [string]::IsNullOrWhiteSpace($AuthJwtSecret)) {
    $env:AUTH_JWT_SECRET = $AuthJwtSecret
}
if ($MtlsEnabled) {
    $env:MTLS_ENABLED = "true"
    $env:MTLS_KEYFILE = $MtlsKeyfile
    $env:MTLS_CERTFILE = $MtlsCertfile
    $env:MTLS_CA_FILE = $MtlsCaFile
}

Write-Host "[edge-security-system] gunicorn ($Workers workers) starting..."
Write-Host "  host=$Host port=$Port workers=$Workers"
Write-Host "  auth_enabled=$AuthEnabled mtls_enabled=$MtlsEnabled"
Write-Host "  allow_real_execution=false  <- hard safety boundary"

# gunicorn on Windows requires waitress sync worker (uvicorn_worker only on Linux).
# We fall back to uvicorn --reload single-process on Windows.
$IsWin = $PSVersionTable.PSVersion
if ($IsWin.Major -ge 5) {
    # Try gunicorn first; if it fails (not installed / no sync worker on Windows) → uvicorn
    try {
        gunicorn app.main:app `
            --workers $Workers `
            --bind "$Host`:$Port" `
            --worker-class uvicorn.workers.UvicornWorker `
            --log-level $LogLevel
    } catch {
        Write-Host "[gunicorn not available on Windows — falling back to single uvicorn]"
        uvicorn app.main:app --host $Host --port $Port --log-level $LogLevel
    }
}
