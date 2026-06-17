#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/scripts/stop-all.sh
# Stop every agent first, then the shared stack last.
# Shared services are torn down last so agents shut down cleanly while their
# database/cache are still reachable.
# ──────────────────────────────────────────────────────────────────────────
set -e

echo "=== Stopping Agents ==="
for dir in /opt/*/; do
  dirname=$(basename "$dir")
  if [ "$dirname" != "shared" ] && [ -f "$dir/docker-compose.yml" ]; then
    echo "Stopping $dirname..."
    cd "$dir"
    sudo podman-compose down
  fi
done

echo ""
echo "=== Stopping Shared Services ==="
cd /opt/shared
sudo podman-compose down

echo ""
echo "=== Status ==="
sudo podman ps --format "table {{.Names}}\t{{.Status}}"
