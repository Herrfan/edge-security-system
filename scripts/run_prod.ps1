# Phase 11 — production-style launch script (PowerShell, Windows).
#
#   .\scripts\run_prod.ps1  (or from repo root: scripts\run_prod.ps1)
#
# Hard safety default: allow_real_execution=False is baked into Settings.

param(
    [string]$Host = "0.0.0.0",
    [int]$Port = 8000,
    [int]$Workers = 1,  # uvicorn workers flag ignored on Windows; --reload works instead
    [string]$LogLevel = "WARNING",
    [bool]$AuthEnabled = $false,
    [bool]$MetricsPersistEnabled = $false,
    [string]$AuthJwtSecret = ""
)

$ErrorActionPreference = "Stop"
Set-Location "$PSScriptRoot\.."

$env:APP_ENV = "production"
$env:APP_LOG_LEVEL = $LogLevel
$env:AUTH_ENABLED = $AuthEnabled.ToString().ToLower()
$env:METRICS_PERSIST_ENABLED = $MetricsPersistEnabled.ToString().ToLower()

if ($AuthEnabled -and [string]::IsNullOrWhiteSpace($AuthJwtSecret)) {
    Write-Error "AUTH_ENABLED=true but AUTH_JWT_SECRET is empty → aborting"
    exit 1
}
if (-not [string]::IsNullOrWhiteSpace($AuthJwtSecret)) {
    $env:AUTH_JWT_SECRET = $AuthJwtSecret
}

Write-Host "[edge-security-system] starting..."
Write-Host "  host=$Host port=$Port env=production log=$LogLevel"
Write-Host "  auth_enabled=$AuthEnabled metrics_persist=$MetricsPersistEnabled"
Write-Host "  allow_real_execution=false  <- hard safety boundary"

# On Windows uvicorn --workers is best-effort; single-process is fine for dev-box testing
uvicorn app.main:app --host $Host --port $Port --log-level $LogLevel
