#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/scripts/check-health.sh
# Probe the shared nginx /health endpoint and each known agent endpoint.
# ──────────────────────────────────────────────────────────────────────────
BASE="${1:-http://localhost}"

probe() {
  local label=$1
  local url=$2
  code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
  if [ "$code" = "200" ] || [ "$code" = "301" ] || [ "$code" = "302" ]; then
    printf "  [ OK  ] %-22s %s (%s)\n" "$label" "$url" "$code"
  else
    printf "  [FAIL ] %-22s %s (%s)\n" "$label" "$url" "$code"
  fi
}

echo "=== Container status ==="
sudo podman ps --format "table {{.Names}}\t{{.Status}}"

echo ""
echo "=== Endpoint health (base: $BASE) ==="
probe "nginx /health"        "$BASE/health"
probe "compliance frontend"  "$BASE/compliance/"
probe "compliance api"       "$BASE/compliance/api/docs"
probe "seo frontend"         "$BASE/seo/"
probe "seo api"              "$BASE/seo/api/docs"

echo ""
echo "=== Shared service probes ==="
if sudo podman exec shared-postgres pg_isready -U postgres >/dev/null 2>&1; then
  echo "  [ OK  ] postgres (pg_isready)"
else
  echo "  [FAIL ] postgres (pg_isready)"
fi
if sudo podman exec shared-redis redis-cli ping 2>/dev/null | grep -q PONG; then
  echo "  [ OK  ] redis (ping)"
else
  echo "  [FAIL ] redis (ping)"
fi
