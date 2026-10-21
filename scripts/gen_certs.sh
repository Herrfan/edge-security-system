#!/usr/bin/env bash
# Phase 14 — generate self-signed mTLS certs for testing.
#
# CA + server cert + client cert (CN="edge-client"). All stored in ./certs/
# Certs are self-signed — DO NOT use in production (use your real CA).

set -euo pipefail
cd "$(dirname "$0")/.."

OUT_DIR="certs"
CN_SERVER="${CN_SERVER:-edge-server}"
CN_CLIENT="${CN_CLIENT:-edge-client}"

mkdir -p "$OUT_DIR"

echo "[mTLS] Generating CA key + self-signed CA cert..."
openssl genrsa -out "$OUT_DIR/ca.key" 2048 2>/dev/null
openssl req -new -x509 -key "$OUT_DIR/ca.key" \
    -out "$OUT_DIR/ca.crt" -days 3650 \
    -subj "/CN=edge-ca"

echo "[mTLS] Generating server cert..."
openssl genrsa -out "$OUT_DIR/server.key" 2048 2>/dev/null
openssl req -new -key "$OUT_DIR/server.key" \
    -out "$OUT_DIR/server.csr" \
    -subj "/CN=$CN_SERVER"
openssl x509 -req -in "$OUT_DIR/server.csr" \
    -CA "$OUT_DIR/ca.crt" -CAkey "$OUT_DIR/ca.key" -CAcreateserial \
    -out "$OUT_DIR/server.crt" -days 365 \
    -extfile <(printf "subjectAltName=DNS:$CN_SERVER,IP:127.0.0.1")

echo "[mTLS] Generating client cert (CN=$CN_CLIENT)..."
openssl genrsa -out "$OUT_DIR/client.key" 2048 2>/dev/null
openssl req -new -key "$OUT_DIR/client.key" \
    -out "$OUT_DIR/client.csr" \
    -subj "/CN=$CN_CLIENT"
openssl x509 -req -in "$OUT_DIR/client.csr" \
    -CA "$OUT_DIR/ca.crt" -CAkey "$OUT_DIR/ca.key" -CAcreateserial \
    -out "$OUT_DIR/client.crt" -days 365

echo "[mTLS] Done. Certs in $OUT_DIR:"
ls -l "$OUT_DIR"
echo
echo "To start uvicorn with mTLS (both server & client certs):"
echo "  uvicorn app.main:app --ssl-keyfile $OUT_DIR/server.key --ssl-certfile $OUT_DIR/server.crt --ssl-ca-certs $OUT_DIR/ca.crt"
echo
echo "To call it with curl:"
echo "  curl --cert $OUT_DIR/client.crt --key $OUT_DIR/client.key --cacert $OUT_DIR/ca.crt https://localhost:8000/health"
