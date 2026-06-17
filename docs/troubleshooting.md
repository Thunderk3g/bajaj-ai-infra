# Troubleshooting

Common issues on the RHEL9 + Podman deployment and how to fix them.

## Quick triage

```bash
# What's running?
sudo podman ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Health of all endpoints
sudo bash /opt/shared/scripts/check-health.sh

# Logs for a specific container
sudo podman logs --tail 100 shared-nginx
sudo podman logs --tail 100 compliance-backend
```

---

## Image errors

### `Error: ... image not known` / pull errors

Compose files use `pull_policy: never`, so the image must already exist
locally. Pre-pull base images and (re)build agent images:

```bash
sudo bash /opt/shared/scripts/pre-pull-images.sh
cd /opt/compliance-agent && sudo podman-compose build
```

---

## Network errors

### `network shared-network not found`

An agent was started before the shared stack. Bring up shared first:

```bash
cd /opt/shared && sudo podman-compose up -d
cd /opt/compliance-agent && sudo podman-compose up -d
```

The agent compose files use `external: true` — they do **not** create the
network, they join the one owned by `shared/docker-compose.yml`.

### Containers can't reach each other

They must all be on `shared-network`. Verify:

```bash
sudo podman network inspect shared-network
```

Reach services by container name: `shared-postgres:5432`, `shared-redis:6379`,
`<agent>-backend:<port>`.

---

## Nginx issues

### 502 Bad Gateway on /<agent>/

The agent container is down or the upstream port is wrong.

```bash
sudo podman ps | grep <agent>
sudo podman logs --tail 50 <agent>-frontend
```

Confirm the `upstream` port in `nginx.conf` matches the container's port and
the port in `docs/port-registry.md`.

### Route changes not taking effect

Reload (do **not** restart) nginx after editing `nginx.conf`:

```bash
sudo podman exec shared-nginx nginx -t      # validate first
sudo podman exec shared-nginx nginx -s reload
```

### `nginx -t` fails after add-agent-route.sh

The script writes a backup to `nginx.conf.bak` and restores it on failure.
Inspect the diff, fix the markers, and re-run. Markers
`# BEGIN/END UPSTREAMS` and `# BEGIN/END LOCATIONS` must remain intact.

---

## Database issues

### New agent DB missing

`init-db.sh` only runs on the **first** postgres start. For an
already-initialized postgres, create the database manually:

```bash
sudo podman exec -it shared-postgres psql -U postgres \
  -c "CREATE DATABASE <agent>_db;"
sudo podman exec -it shared-postgres psql -U postgres -d <agent>_db \
  -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

### `password authentication failed`

`POSTGRES_PASSWORD` in the agent's `.env` must match `shared/.env`. Update and
restart the agent:

```bash
cd /opt/<agent>-agent && sudo podman-compose up -d --force-recreate
```

### `extension "vector" is not available`

The postgres image must be `docker.io/pgvector/pgvector:pg15` (it ships
pgvector). Confirm with `sudo podman inspect shared-postgres | grep Image`.

---

## Redis issues

### Backend can't connect to redis

Check it's up and responding:

```bash
sudo podman exec shared-redis redis-cli ping     # expect PONG
```

`REDIS_URL` should be `redis://shared-redis:6379`.

---

## Podman / SELinux (RHEL9 specifics)

### Volume mount permission denied (SELinux)

RHEL9 enforces SELinux. If a bind-mounted file (e.g. `nginx.conf`,
`init-db.sh`) is unreadable inside the container, add the `:Z` or `:ro` relabel
suffix, or check labels with `ls -Z`. The compose files already mount config
read-only (`:ro`).

### Containers don't survive reboot

Ensure the podman socket / restart policy is active. Compose uses
`restart: always`; for boot persistence enable the podman restart service:

```bash
sudo systemctl enable --now podman-restart.service
```

### `podman-compose: command not found`

Install it:

```bash
sudo dnf install -y podman-compose
# or: pip3 install podman-compose
```

---

## Full reset (last resort)

```bash
cd /opt/shared && sudo bash scripts/stop-all.sh
# WARNING: removing volumes deletes ALL agent data
sudo podman volume rm shared-pgdata shared-redisdata
cd /opt/shared && sudo bash scripts/start-all.sh
```
