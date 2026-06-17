#!/usr/bin/env bash
# Om / operators — quick production deployment health check. Exit non-zero on critical failure.
set -euo pipefail

DOMAIN="${DOMAIN:-}"
GRAFANA_URL="${GRAFANA_URL:-}"
FAILED=0

fail() { echo "FAIL: $*"; FAILED=1; }
ok()   { echo "OK:   $*"; }

command -v kubectl >/dev/null || fail "kubectl missing"
command -v minikube >/dev/null || fail "minikube missing"

minikube status >/dev/null 2>&1 || fail "minikube not running"
ok "minikube running"

# App pods
NOT_READY=$(kubectl get pods -n sunny-prod --no-headers 2>/dev/null | grep -vE 'Running|Completed' | wc -l || true)
[[ "$NOT_READY" -eq 0 ]] && ok "sunny-prod pods Running" || fail "sunny-prod has $NOT_READY non-Running pods"

# Observability
kubectl get pods -n observability --no-headers 2>/dev/null | grep -q Running && ok "observability pods Running" || fail "observability stack unhealthy"

# Gateway health via minikube service (if configured)
if kubectl get svc -n sunny-prod gateway 2>/dev/null | grep -q NodePort; then
  GW_PORT=$(kubectl get svc -n sunny-prod gateway -o jsonpath='{.spec.ports[0].nodePort}')
  MINIKUBE_IP=$(minikube ip)
  curl -fsS "http://${MINIKUBE_IP}:${GW_PORT}/management/health" | grep -q UP && ok "gateway health UP" || fail "gateway health check"
fi

# Public edge (when DOMAIN set)
if [[ -n "$DOMAIN" ]]; then
  curl -fsS "https://${DOMAIN}/api/management/health" | grep -q UP && ok "public /api health" || fail "public API health"
  curl -fsS "https://${DOMAIN}/progress.json" | grep -q runId && ok "progress.json live" || fail "progress.json"
fi

# Grafana reachability
if [[ -n "$GRAFANA_URL" ]]; then
  curl -fsS -o /dev/null -w "%{http_code}" "${GRAFANA_URL}/api/health" | grep -q 200 && ok "Grafana health" || fail "Grafana unreachable"
fi

exit "$FAILED"
