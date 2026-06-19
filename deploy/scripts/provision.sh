#!/usr/bin/env bash
# Idempotent host provisioning stub — Suresh extends with OS-specific installs.
# Safe to re-run; skips tools already at required versions.
set -euo pipefail

echo "=== Sunny provision.sh (stub) ==="
echo "Suresh completes this script with apt/yum installs for:"
echo "  Java, Maven/Gradle, Node/npm, PostgreSQL, Nginx, PM2, Docker, certbot, curl, jq, openssl"
echo ""
echo "Verify only (no installs in stub):"
command -v java >/dev/null && java -version 2>&1 | head -1 || echo "MISSING: java"
command -v node >/dev/null && node -v || echo "MISSING: node"
command -v docker >/dev/null && docker -v || echo "MISSING: docker"
command -v kubectl >/dev/null && kubectl version --client 2>/dev/null | head -1 || echo "MISSING: kubectl"
command -v minikube >/dev/null && minikube version --short 2>/dev/null || echo "MISSING: minikube"
command -v helm >/dev/null && helm version --short 2>/dev/null || echo "MISSING: helm"
command -v nginx >/dev/null && nginx -v 2>&1 || echo "MISSING: nginx"
command -v pm2 >/dev/null && pm2 -v || echo "MISSING: pm2"
command -v psql >/dev/null && psql --version || echo "MISSING: psql"
