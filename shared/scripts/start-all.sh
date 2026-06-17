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
  [ "$dirname" = "shared" ] && continue
  # Prefer an agent's shared-infra compose file when it ships one; fall back to
  # the default docker-compose.yml otherwise. This keeps a standalone
  # docker-compose.yml (own postgres) from being launched by mistake.
  if   [ -f "$dir/docker-compose.shared.yml" ]; then cf="docker-compose.shared.yml"
  elif [ -f "$dir/docker-compose.yml" ];        then cf="docker-compose.yml"
  else continue
  fi
  echo "Starting $dirname ($cf)..."
  cd "$dir"
  sudo podman-compose -f "$cf" up -d
done

echo ""
echo "=== Reloading Nginx Routes ==="
sudo podman exec shared-nginx nginx -s reload

echo ""
echo "=== Status ==="
sudo podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
