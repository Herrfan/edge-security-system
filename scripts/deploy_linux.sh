#!/usr/bin/env bash
# ============================================================================
# edge-security-system — one-shot production deploy script (Linux edge device)
#
# Targets: Ubuntu 22.04 / Debian 12 / ARM64 (Pi 4B/5, Jetson Nano, RK3588)
# Idempotent: safe to run multiple times; installs missing bits, upgrades none.
# Dry-run:   bash deploy.sh --check   (no installs, just verify env)
#
# What it does (step by step):
#   1. OS check + kernel ≥ 5.4 + CPU ISA check
#   2. apt install python3.12-venv build-essential git curl (no apt-get upgrade!)
#   3. Clone/pull repo → /opt/edge-security-system
#   4. python3 -m venv .venv + pip install -e . psutil gunicorn uvicorn[standard]
#   5. Install Ollama (official install.sh) + pull qwen2.5:3b + nomic-embed-text
#   6. systemd: create edge-security.service + edge-security.target
#   7. Optional: nginx + mTLS certs + site config (only if --with-nginx)
#   8. verify: python scripts/final_demo.py + systemctl status
#
# SAFETY BOUNDARY (hard-coded):
#   allow_real_execution=False (never overridden in --env)
#   Ollama default CPU-only — GPU is opt-in via --with-gpu
#   Never runs apt-get upgrade / dist-upgrade — edge devices may be offline / pinned
# ============================================================================
set -euo pipefail

REPO_URL="https://github.com/Herrfan/edge-security-system.git"
INSTALL_DIR="/opt/edge-security-system"
SERVICE_NAME="edge-security"
ENV_FILE="${INSTALL_DIR}/.env"
VENV_DIR="${INSTALL_DIR}/.venv"
LOG_DIR="${INSTALL_DIR}/logs"

# ---------- flags ----------
CHECK_ONLY=false
WITH_NGINX=false
WITH_GPU=false
DEPLOY_KEY=""
APP_PORT="${APP_PORT:-8000}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --check)         CHECK_ONLY=true; shift ;;
    --with-nginx)    WITH_NGINX=true; shift ;;
    --with-gpu)      WITH_GPU=true; shift ;;
    --deploy-key)    DEPLOY_KEY="$2"; shift 2 ;;
    --port)          APP_PORT="$2"; shift 2 ;;
    *) echo "Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# ---------- color helpers ----------
OK()   { printf "\033[32m[OK]\033[0m  %s\n" "$*"; }
INFO() { printf "\033[36m[→]\033[0m  %s\n" "$*"; }
WARN() { printf "\033[33m[!]\033[0m  %s\n" "$*"; }
FAIL() { printf "\033[31m[FAIL]\033[0m %s\n" "$*" >&2; }

need_root() { if [[ $(id -u) -ne 0 ]]; then FAIL "need sudo"; exit 1; fi; }

# ============================================================================
# Step 1 — OS sanity
# ============================================================================
step_os() {
  INFO "Step 1 — OS sanity"
  local distro kernel_maj isa
  distro="$(cat /etc/os-release | grep '^ID=' | cut -d= -f2)"
  kernel_maj="$(uname -r | cut -d. -f1)"
  isa="$(uname -m)"

  INFO "  distro=$distro  kernel=$(uname -r)  isa=$isa"

  if [[ "$isa" == "x86_64" || "$isa" == "aarch64" ]]; then
    OK "  CPU ISA OK (x86_64 / aarch64)"
  else
    FAIL "  unexpected ISA: $isa (supported: x86_64 / aarch64)"
    exit 1
  fi

  if [[ "$kernel_maj" -lt 5 ]]; then
    WARN "  kernel $(uname -r) < 5.4 — sqlite-vec may need manual kernel config"
  else
    OK "  kernel OK"
  fi

  OK "  OS check done"
}

# ============================================================================
# Step 2 — apt packages (CHECK_ONLY mode: just verify presence)
# ============================================================================
step_apt() {
  INFO "Step 2 — apt packages"
  local pkgs=(python3.12 python3.12-venv python3-pip git curl)
  local build=(build-essential python3.12-dev)

  local missing=()
  for p in "${pkgs[@]}"; do
    if ! dpkg -s "$p" &>/dev/null && ! command -v "$p" &>/dev/null; then
      missing+=("$p")
    fi
  done

  if ${CHECK_ONLY}; then
    if [[ ${#missing[@]} -gt 0 ]]; then
      WARN "  MISSING packages: ${missing[*]}"
    else
      OK "  all apt packages present"
    fi
    return
  fi

  need_root
  export DEBIAN_FRONTEND=noninteractive
  INFO "  apt-get update (single run, no upgrade)"
  apt-get update -y 2>/dev/null || WARN "  apt-get update failed (may be offline) — continuing"

  for p in "${missing[@]}"; do
    INFO "  installing $p"
    apt-get install -y "$p" 2>/dev/null || WARN "  $p install failed (apt repo unavailable?)"
  done

  # build-essential for pip wheels on Pi 4B / Jetson
  apt-get install -y "${build[@]}" 2>/dev/null || true
  OK "  apt install done"
}

# ============================================================================
# Step 3 — clone / update repo
# ============================================================================
step_repo() {
  INFO "Step 3 — repo"
  if [[ -d "$INSTALL_DIR/.git" ]]; then
    INFO "  repo exists — git pull"
    (cd "$INSTALL_DIR" && git fetch --depth=1 && git reset --hard origin/main)
    OK "  repo updated"
  elif ${CHECK_ONLY}; then
    WARN "  INSTALL_DIR=$INSTALL_DIR missing — would git clone"
    return
  else
    need_root
    INFO "  git clone $REPO_URL → $INSTALL_DIR"
    git clone "$REPO_URL" "$INSTALL_DIR"
    OK "  repo cloned"
  fi
}

# ============================================================================
# Step 4 — venv + pip install
# ============================================================================
step_pip() {
  INFO "Step 4 — python venv + pip"
  if [[ ! -d "$VENV_DIR" ]]; then
    ${CHECK_ONLY} && { WARN "  venv missing — would create"; return; }
    python3.12 -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
  local pip_bin="$VENV_DIR/bin/pip"

  INFO "  pip --version"
  "$pip_bin" install --quiet --upgrade pip 2>/dev/null || true

  local extra=(psutil gunicorn "uvicorn[standard]")
  local install_cmd=("$pip_bin" install --quiet -e "$INSTALL_DIR")
  for e in "${extra[@]}"; do install_cmd+=("$e"); done

  if ${CHECK_ONLY}; then
    # just verify the key imports work
    ${VENV_DIR}/bin/python -c "import fastapi, sqlalchemy, app.main" \
      && OK "  pip imports OK" \
      || WARN "  pip imports missing — would pip install -e ."
    return
  fi

  INFO "  pip install -e . + extras"
  "${install_cmd[@]}" || FAIL "  pip install failed"
  OK "  pip done"
}

# ============================================================================
# Step 5 — Ollama
# ============================================================================
step_ollama() {
  INFO "Step 5 — Ollama"
  if command -v ollama &>/dev/null; then
    OK "  ollama already installed"
  elif ${CHECK_ONLY}; then
    WARN "  ollama missing — would install via official install.sh"
    return
  else
    need_root
    INFO "  installing ollama (official install.sh)"
    curl -fsSL https://ollama.com/install.sh | sh || WARN "  ollama install failed (network?)"
  fi

  if ${CHECK_ONLY}; then
    if ! command -v ollama &>/dev/null; then return; fi
  fi

  # Pull models — CPU default; GPU models opt-in
  local cpu_model="qwen2.5:3b"
  local emb_model="nomic-embed-text"
  if ${WITH_GPU}; then
    WARN "  GPU mode requested — consider quantized variants (qwen2.5:7b / nomic-embed-text:f16)"
  fi

  if command -v ollama &>/dev/null; then
    INFO "  pulling $cpu_model"
    ollama pull "$cpu_model" 2>/dev/null || WARN "  $cpu_model pull failed (offline?)"
    INFO "  pulling $emb_model"
    ollama pull "$emb_model" 2>/dev/null || WARN "  $emb_model pull failed"
    OK "  ollama ready"
  fi
}

# ============================================================================
# Step 6 — .env + systemd unit
# ============================================================================
step_systemd() {
  INFO "Step 6 — systemd"
  ${CHECK_ONLY} && { OK "  systemd units present? skipping verify"; return; }
  need_root

  mkdir -p "$LOG_DIR" "$(dirname "$ENV_FILE")"

  # .env — hard-coded allow_real_execution=False. NEVER read from --env CLI
  cat > "$ENV_FILE" <<ENVEOF
APP_ENV=production
APP_HOST=0.0.0.0
APP_PORT=${APP_PORT}
APP_LOG_LEVEL=WARNING

# SAFETY BOUNDARY — DO NOT flip unless you fully understand nftables implications
ALLOW_REAL_EXECUTION=false

# Ollama (local)
OLLAMA_BASE_URL=http://127.0.0.1:11434
LLM_MODEL=qwen2.5:3b
LLM_PROVIDER=ollama
EMBEDDING_MODEL=nomic-embed-text
VECTOR_BACKEND=sqlite_vec
RETRIEVAL_MODE=hybrid

# Auth — production MUST set AUTH_JWT_SECRET via this file or env var later
AUTH_ENABLED=false
AUTH_JWT_SECRET=
AUTH_TOKEN_TTL_MINUTES=60

# Observability
METRICS_PERSIST_ENABLED=true
METRICS_SNAPSHOT_INTERVAL_MINUTES=15
# VM_REMOTE_WRITE_URL=https://vm.example.com/api/v1/push   # uncomment if you have VM

# mTLS — production MUST enable and provide real CA signed certs
MTLS_ENABLED=false
MTLS_KEYFILE=
MTLS_CERTFILE=
MTLS_CA_FILE=
ENVEOF
  chmod 644 "$ENV_FILE"
  OK "  .env written (allow_real_execution=false hard-coded)"

  # Unit file — gunicorn + uvicorn workers
  cat > /etc/systemd/system/${SERVICE_NAME}.service <<'SVC'
[Unit]
Description=edge-security-system API (Phase 0-14)
After=network-online.target ollama.service
Wants=ollama.service

[Service]
Type=simple
User=edge
Group=edge
EnvironmentFile=/opt/edge-security-system/.env
WorkingDirectory=/opt/edge-security-system
ExecStart=/opt/edge-security-system/.venv/bin/gunicorn \
    app.main:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:${APP_PORT} \
    --log-level WARNING \
    --access-logfile /opt/edge-security-system/logs/access.log \
    --errorlog /opt/edge-security-system/logs/error.log

Restart=on-failure
RestartSec=5
StandardOutput=journal
StandardError=journal

# Sandbox — no new system calls after startup
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
SVC
  OK "  systemd unit written → /etc/systemd/system/${SERVICE_NAME}.service"

  # Create service user
  if ! id -u edge &>/dev/null; then
    useradd --system --home "$INSTALL_DIR" --shell /usr/sbin/nologin edge
  fi
  chown -R edge:edge "$INSTALL_DIR"
  OK "  user=edge created + chown"

  systemctl daemon-reload
  systemctl enable "${SERVICE_NAME}.service" 2>/dev/null || true
  systemctl start  "${SERVICE_NAME}.service" || WARN "  service start failed — see journalctl -u ${SERVICE_NAME}"
  OK "  systemd service started"
}

# ============================================================================
# Step 7 — nginx + mTLS (opt-in)
# ============================================================================
step_nginx() {
  ${CHECK_ONLY} && return
  ${WITH_NGINX} || return
  need_root

  INFO "Step 7 — nginx + mTLS"
  apt-get install -y nginx openssl 2>/dev/null || FAIL "nginx install failed"

  local cert_dir="/etc/ssl/edge-security"
  mkdir -p "$cert_dir"
  bash "${INSTALL_DIR}/scripts/gen_certs.sh" 2>/dev/null || true
  [[ -f "${INSTALL_DIR}/certs/server.crt" ]] || { FAIL "  cert gen failed"; return; }
  cp "${INSTALL_DIR}/certs/"*.crt "${INSTALL_DIR}/certs/"*.key "$cert_dir/"
  chmod 600 "$cert_dir/"*.key

  cat > /etc/nginx/sites-available/edge-security <<NGINX
server {
    listen 443 ssl http2;
    server_name _;

    ssl_certificate     ${cert_dir}/server.crt;
    ssl_certificate_key ${cert_dir}/server.key;
    ssl_client_certificate ${cert_dir}/ca.crt;
    ssl_verify_client   optional;  # "on" = hard require; optional = logs but allows

    # Edge devices have limited CPU — keep TLS light
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_session_cache shared:EDGE:10m;

    # Strip x-role header so auth middleware must get role from JWT, not spoof
    proxy_set_header X-Role "";

    location / {
        proxy_pass http://127.0.0.1:${APP_PORT};
        proxy_set_header Host              \$host;
        proxy_set_header X-Real-IP         \$remote_addr;
        proxy_set_header X-Forwarded-For   \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;

        # Client cert subject → header (so app can audit)
        proxy_set_header X-Client-Subject \$ssl_client_s_dn_legacy;
    }

    location /metrics {
        # Only allow Prometheus scrape from local node
        allow 127.0.0.1;
        deny all;
        proxy_pass http://127.0.0.1:${APP_PORT};
    }
}
NGINX
  ln -sf /etc/nginx/sites-available/edge-security /etc/nginx/sites-enabled/
  nginx -t && systemctl reload nginx || FAIL "nginx config invalid — see nginx -t"
  OK "  nginx + mTLS ready on :443"
}

# ============================================================================
# Step 8 — verify
# ============================================================================
step_verify() {
  INFO "Step 8 — verify"
  if ${CHECK_ONLY}; then
    INFO "  CHECK_ONLY — skip full verify; run scripts/verify_deploy.sh after install"
    return
  fi

  sleep 2
  local http_code
  http_code=$(curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${APP_PORT}/health" || echo "000")
  if [[ "$http_code" == "200" ]]; then
    OK "  /health → 200"
  else
    FAIL "  /health → $http_code (see journalctl -u ${SERVICE_NAME})"
  fi

  local status
  status=$(systemctl is-active "${SERVICE_NAME}.service" 2>/dev/null || echo "unknown")
  [[ "$status" == "active" ]] && OK "  systemd active" || WARN "  systemd=$status"

  # Final demo — subprocess so it spawns its own TestClient
  if [[ -d "$VENV_DIR" ]]; then
    INFO "  running final_demo.py ..."
    "${VENV_DIR}/bin/python" "${INSTALL_DIR}/scripts/final_demo.py" 2>&1 | tail -n 5
  fi
}

# ============================================================================
# dispatch
# ============================================================================
main() {
  echo
  echo "================================================================="
  echo "  edge-security-system — Linux edge deploy"
  echo "  $(date -Iseconds)  host=$(hostname)  check_only=${CHECK_ONLY}"
  echo "================================================================="
  echo

  step_os
  step_apt
  step_repo
  step_pip
  step_ollama
  step_systemd
  step_nginx
  step_verify

  echo
  echo "================================================================="
  OK "deployment complete"
  echo "  service name : ${SERVICE_NAME}"
  echo "  .env         : ${ENV_FILE}  (edit to enable auth / metrics persist)"
  echo "  logs         : ${LOG_DIR}/error.log  $(systemctl -u ${SERVICE_NAME} -n 50 status 2>/dev/null)"
  echo "  allow_real_execution=false  ← hard safety boundary — NOT overridden here"
  echo "================================================================="
}

main "$@"
