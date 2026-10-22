#!/usr/bin/env bash
# Post-deploy health check — run from target edge device after deploy.sh finishes.
set -euo pipefail

PORT="${PORT:-8000}"
BASE="http://127.0.0.1:${PORT}"
PASS=0; FAIL=0

ok()  { PASS=$((PASS+1)); printf "\033[32m[PASS]\033[0m %s\n" "$*"; }
bad() { FAIL=$((FAIL+1)); printf "\033[31m[FAIL]\033[0m %s\n" "$*"; }

check() {
  local path="$1" expect="$2" label="$3"
  local code
  code=$(curl -s -o /tmp/_chk.json -w "%{http_code}" "${BASE}${path}" || echo "000")
  if [[ "$code" == "$expect" ]]; then ok "$label ($code)"; else bad "$label → $code"; fi
}

echo "--- edge-security-system verify ---"
check "/health"              "200" "health"
check "/"                    "200" "index"
check "/docs"                "200" "swagger"
check "/api/v1/retrieval/status" "200" "retrieval status"
check "/metrics"             "200" "prometheus text"

if systemctl is-active --quiet edge-security.service; then
  ok "systemd edge-security.service active"
else
  bad "systemd not active — journalctl -u edge-security -n 50"
fi

if curl -s http://127.0.0.1:11434/api/tags -o /dev/null -w "%{http_code}" | grep -q "200"; then
  ok "ollama reachable"
else
  bad "ollama not reachable — systemctl status ollama"
fi

echo "--- $PASS/$((PASS+FAIL)) passed ---"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
