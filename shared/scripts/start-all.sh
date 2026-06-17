#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/scripts/start-all.sh
# Start the shared stack, wait for it to be healthy, then start every agent,
# then reload nginx so all routes are live.
# ──────────────────────────────────────────────────────────────────────────
set -e

echo "=== Starting Shared Services ==="
cd /opt/shared
sudo podman-compose up -d

echo "Waiting for postgres..."
until sudo podman exec shared-postgres pg_isready -U postgres 2>/dev/null; do
  printf '.'
  sleep 2
done
echo " ready"

echo "Waiting for redis..."
until sudo podman exec shared-redis redis-cli ping 2>/dev/null | grep -q PONG; do
  printf '.'
  sleep 2
done
echo " ready"

echo ""
echo "=== Starting Agents ==="
for dir in /opt/*/; do
  dirname=$(basename "$dir")
  if [ "$dirname" != "shared" ] && [ -f "$dir/docker-compose.yml" ]; then
    echo "Starting $dirname..."
    cd "$dir"
    sudo podman-compose up -d
  fi
done

echo ""
echo "=== Reloading Nginx Routes ==="
sudo podman exec shared-nginx nginx -s reload

echo ""
echo "=== Status ==="
sudo podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
