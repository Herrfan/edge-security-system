#!/usr/bin/env bash
# Rollback — remove systemd + nginx + user + logs. KEEPS repo + venv + ollama models.
set -euo pipefail

INSTALL_DIR="/opt/edge-security-system"
SERVICE_NAME="edge-security"

step() { printf "\033[36m[rollback]\033[0m %s\n" "$*"; }

sudo_cmd() { sudo "$@"; }

step "stop + disable systemd"
sudo_cmd systemctl stop "${SERVICE_NAME}.service"     2>/dev/null || true
sudo_cmd systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
sudo_cmd rm -f /etc/systemd/system/${SERVICE_NAME}.service
sudo_cmd systemctl daemon-reload

step "nginx site"
sudo_cmd rm -f /etc/nginx/sites-enabled/edge-security 2>/dev/null || true
sudo_cmd rm -f /etc/nginx/sites-available/edge-security 2>/dev/null || true
sudo_cmd nginx -t 2>/dev/null && sudo_cmd systemctl reload nginx 2>/dev/null || true

step "service user"
sudo_cmd userdel -r edge 2>/dev/null || true

step "keep repo + venv + models at $INSTALL_DIR"
ls -ld "$INSTALL_DIR"

echo "--- rollback done — to fully wipe: rm -rf $INSTALL_DIR + ollama rm $(ollama list -q 2>/dev/null | tr '\n' ' ')"
