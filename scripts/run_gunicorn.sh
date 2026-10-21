#!/usr/bin/env bash
# Phase 14 — Gunicorn launcher (Linux / macOS).
#
# Install: pip install gunicorn uvicorn
# Usage:   bash scripts/run_gunicorn.sh --workers 4 --port 8000 --auth-enabled

set -euo pipefail
cd "$(dirname "$0")/.."

WORKERS="${WORKERS:-4}"
PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"
LOG_LEVEL="${LOG_LEVEL:-WARNING}"

# Parse simple flags; --auth-enabled and --mtls need env var set explicitly
AUTH_FLAG=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    -w|--workers) WORKERS="$2"; shift 2 ;;
    -p|--port)    PORT="$2"; shift 2 ;;
    -h|--host)    HOST="$2"; shift 2 ;;
    -l|--log-level) LOG_LEVEL="$2"; shift 2 ;;
    --auth-enabled) AUTH_FLAG="auth"; shift ;;
    --mtls) AUTH_FLAG="mtls"; shift ;;
    *) shift ;;
  esac
done

export APP_ENV=production
export APP_LOG_LEVEL="$LOG_LEVEL"
export AUTH_ENABLED="${AUTH_ENABLED:-false}"
export METRICS_PERSIST_ENABLED="${METRICS_PERSIST_ENABLED:-false}"

if [[ "$AUTH_FLAG" == "auth" ]]; then
  if [[ -z "${AUTH_JWT_SECRET:-}" ]]; then
    echo "ERROR: --auth-enabled needs AUTH_JWT_SECRET env var" >&2
    exit 1
  fi
  export AUTH_ENABLED=true
fi

echo "[edge-security-system] gunicorn ($WORKERS workers) starting..."
echo "  host=$HOST port=$PORT workers=$WORKERS log=$LOG_LEVEL"
echo "  AUTH_ENABLED=$AUTH_ENABLED MTLS_ENABLED=${MTLS_ENABLED:-false}"
echo "  allow_real_execution=false  <- hard safety boundary"

exec gunicorn app.main:app \
    --workers "$WORKERS" \
    --bind "$HOST:$PORT" \
    --worker-class uvicorn.workers.UvicornWorker \
    --log-level "$LOG_LEVEL"
