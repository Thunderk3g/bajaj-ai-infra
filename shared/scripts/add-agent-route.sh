#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/scripts/add-agent-route.sh
# Add nginx upstream + location blocks for a new agent, validate, and reload.
#
# Usage:   ./add-agent-route.sh <agentname> <frontend-port> <backend-port>
# Example: ./add-agent-route.sh seo 3002 8001
#
#   <agentname>      short name, no spaces (becomes /<agentname>/ path and
#                    the <agentname>-frontend / <agentname>-backend container names)
#   <frontend-port>  container port the frontend listens on
#   <backend-port>   container port the backend listens on
#
# Inserts between the BEGIN/END UPSTREAMS and BEGIN/END LOCATIONS markers in
# nginx.conf, runs `nginx -t`, then `nginx -s reload`.
# ──────────────────────────────────────────────────────────────────────────
set -e

NGINX_CONF="/opt/shared/nginx.conf"
NGINX_CONTAINER="shared-nginx"
VM_IP="10.3.5.99"

# ── Validate args ──────────────────────────────────────────────────────────
if [ "$#" -ne 3 ]; then
  echo "Usage: $0 <agentname> <frontend-port> <backend-port>"
  echo "Example: $0 seo 3002 8001"
  exit 1
fi

AGENT="$1"
FE_PORT="$2"
BE_PORT="$3"

if [ ! -f "$NGINX_CONF" ]; then
  echo "ERROR: $NGINX_CONF not found. Run this on the VM (or adjust NGINX_CONF)."
  exit 1
fi

# ── Guard against duplicates ───────────────────────────────────────────────
if grep -q "upstream ${AGENT}_frontend" "$NGINX_CONF"; then
  echo "ERROR: routes for '${AGENT}' already exist in $NGINX_CONF. Aborting."
  exit 1
fi

# ── Backup ─────────────────────────────────────────────────────────────────
BACKUP="${NGINX_CONF}.bak"
cp "$NGINX_CONF" "$BACKUP"
echo "Backup written to $BACKUP"

# ── Build the snippets ─────────────────────────────────────────────────────
UPSTREAM_BLOCK="\\
    # ${AGENT} Agent\\
    upstream ${AGENT}_frontend { server ${AGENT}-frontend:${FE_PORT}; }\\
    upstream ${AGENT}_backend  { server ${AGENT}-backend:${BE_PORT};  }\\
"

LOCATION_BLOCK="\\
        # ${AGENT} Agent\\
        location /${AGENT}/ {\\
            proxy_pass http://${AGENT}_frontend/;\\
            include /etc/nginx/proxy_params.conf;\\
        }\\
        location /${AGENT}/api/ {\\
            proxy_pass http://${AGENT}_backend/;\\
            include /etc/nginx/proxy_params.conf;\\
        }\\
"

# ── Insert before the END markers ──────────────────────────────────────────
# sed inserts the block on the line BEFORE the matched END marker.
sed -i "/# END UPSTREAMS/i\\${UPSTREAM_BLOCK}" "$NGINX_CONF"
sed -i "/# END LOCATIONS/i\\${LOCATION_BLOCK}" "$NGINX_CONF"

echo "Inserted upstream + location blocks for '${AGENT}'."

# ── Validate config inside the running nginx container ─────────────────────
echo ""
echo "=== Validating nginx config ==="
if ! sudo podman exec "$NGINX_CONTAINER" nginx -t; then
  echo "ERROR: nginx -t failed. Restoring backup."
  cp "$BACKUP" "$NGINX_CONF"
  exit 1
fi

# ── Reload ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Reloading nginx ==="
sudo podman exec "$NGINX_CONTAINER" nginx -s reload

# ── Report ─────────────────────────────────────────────────────────────────
echo ""
echo "=== Route added for '${AGENT}' ==="
echo "  Frontend : http://${VM_IP}/${AGENT}/"
echo "  Backend  : http://${VM_IP}/${AGENT}/api/"
echo "  API docs : http://${VM_IP}/${AGENT}/api/docs"
echo ""
echo "Remember to also:"
echo "  - add create_db \"${AGENT}_db\" to shared/init-db.sh"
echo "  - update docs/port-registry.md"
echo "  - start the agent:  cd /opt/${AGENT}-agent && sudo podman-compose up -d"
