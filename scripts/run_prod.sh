#!/usr/bin/env bash
# Phase 11 — production-style launch script.
#
# Windows users: use run_prod.ps1 instead.
# Mac/Linux:     bash scripts/run_prod.sh
#
# Hard safety default: allow_real_execution=False is baked into Settings.
# To lift it, pass ALLOW_REAL_EXECUTION=true explicitly.

set -euo pipefail

cd "$(dirname "$0")/.."

# ---- safe defaults ----
export HOST="${HOST:-0.0.0.0}"
export PORT="${PORT:-8000}"
export WORKERS="${WORKERS:-4}"
export APP_ENV="${APP_ENV:-production}"
export LOG_LEVEL="${LOG_LEVEL:-WARNING}"
export AUTH_ENABLED="${AUTH_ENABLED:-false}"  # opt-in
export METRICS_PERSIST_ENABLED="${METRICS_PERSIST_ENABLED:-false}"  # opt-in

echo "[edge-security-system] starting..."
echo "  host=$HOST port=$PORT workers=$WORKERS env=$APP_ENV log=$LOG_LEVEL"
echo "  auth_enabled=$AUTH_ENABLED metrics_persist=$METRICS_PERSIST_ENABLED"
echo "  allow_real_execution=${ALLOW_REAL_EXECUTION:-false}  ← hard safety boundary"

if [ "$AUTH_ENABLED" = "true" ] && [ -z "${AUTH_JWT_SECRET:-}" ]; then
    echo "ERROR: AUTH_ENABLED=true but AUTH_JWT_SECRET is empty → aborting"
    exit 1
fi

exec uvicorn app.main:app \
    --host "$HOST" \
    --port "$PORT" \
    --workers "$WORKERS" \
    --loop uvloop \
    --http httptools \
    --log-level "$LOG_LEVEL" \
    --no-access-log
