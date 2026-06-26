#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/scripts/pre-pull-images.sh
# Pull every base image used across the platform BEFORE first start, so that
# `pull_policy: never` in the compose files can find them locally.
#
# Run on the VM:  sudo bash /opt/shared/scripts/pre-pull-images.sh
# ──────────────────────────────────────────────────────────────────────────
set -e

IMAGES=(
  "docker.io/pgvector/pgvector:pg15"
  "docker.io/library/redis:7-alpine"
  "docker.io/library/nginx:alpine"
  "docker.io/dpage/pgadmin4:latest"
  # Read-only Docker/Podman socket proxy (monitoring-agent):
  "ghcr.io/tecnativa/docker-socket-proxy"
  # Agent base images (used by Dockerfiles):
  "docker.io/library/python:3.11-slim"
  "docker.io/library/node:20-alpine"
)

echo "=== Pre-pulling base images ==="
for img in "${IMAGES[@]}"; do
  echo "Pulling $img ..."
  sudo podman pull "$img"
done

echo ""
echo "=== Done. Local images: ==="
sudo podman images --format "table {{.Repository}}:{{.Tag}}\t{{.Size}}"
