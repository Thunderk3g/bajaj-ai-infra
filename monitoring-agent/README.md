# Monitoring Agent

Read-only, live container monitoring for the platform. Watches every Podman
container on the VM (CPU %, RAM, live logs, metadata) grouped into "agents" by
container-name prefix. **Live only** — no persistent history. The whole section
is gated behind nginx basic-auth, and a GET-only socket-proxy makes engine
access genuinely read-only (no start/stop/restart/exec is possible).

| Component        | Container            | Container Port | Public Path          |
|------------------|----------------------|----------------|----------------------|
| Backend (API)    | `monitoring-backend` | 8002           | `/monitoring/api/`   |
| Socket proxy     | `socket-proxy`       | 2375 (internal)| — (no public route)  |
| UI               | `landing-frontend`   | 80             | `/monitoring`        |

The UI ships inside the existing `landing-frontend` SPA (no new frontend
container); nginx routes `/monitoring` to it. The API contract is frozen in
`docs/superpowers/specs/2026-06-26-agent-monitoring-design.md` §3.

## Architecture

```
Browser ──(basic-auth)──► shared-nginx
   /monitoring       → landing-frontend:80   (SPA route)
   /monitoring/api/  → monitoring-backend:8002
                            │ shared-network (GET only)
                            ▼
                       socket-proxy ──► /run/podman/podman.sock (rootful)
```

## Prerequisites

The shared stack must already be running (`cd /opt/shared && sudo podman-compose up -d`).

### 1. Enable the rootful Podman socket

The socket-proxy mounts `/run/podman/podman.sock`. On RHEL9 enable the **rootful**
socket (this is a system service, not `--user`):

```bash
sudo systemctl enable --now podman.socket
sudo systemctl status podman.socket          # should be active (listening)
ls -l /run/podman/podman.sock                 # should exist
```

### 2. Pre-pull the socket-proxy image

`pull_policy: never` means images must already be local. The base images are in
`shared/scripts/pre-pull-images.sh` (it now includes the socket-proxy):

```bash
sudo bash /opt/shared/scripts/pre-pull-images.sh
# or just the new one:
sudo podman pull ghcr.io/tecnativa/docker-socket-proxy
```

## Deploy

Deploy under `/opt/monitoring-agent` so `start-all.sh` (which loops `/opt/*/`)
picks it up automatically.

```bash
# (on the VM, after git pull into /opt)
cd /opt/monitoring-agent
sudo cp .env.example .env          # defaults are fine; no secrets required

# build + start both containers (backend image is built locally)
sudo podman-compose build
sudo podman-compose up -d
sudo podman ps --filter name=monitoring-backend --filter name=socket-proxy
```

### Generate the basic-auth file

The `/monitoring*` routes use `auth_basic_user_file /etc/nginx/.htpasswd-monitoring`,
which shared-nginx mounts from `shared/.htpasswd-monitoring`. Create it once:

```bash
cd /opt/shared
# -c CREATES the file (truncates!). Use it only for the first user.
htpasswd -c .htpasswd-monitoring monitor
# add more users WITHOUT -c so you don't wipe the file:
htpasswd .htpasswd-monitoring alice
```

> If `htpasswd` is missing: `sudo dnf install -y httpd-tools`.

A committed placeholder `shared/.htpasswd-monitoring.example` documents the
format. The real `.htpasswd-monitoring` is git-ignored — never commit credentials.

### Reload nginx

The `/monitoring` and `/monitoring/api/` routes already exist in
`shared/nginx.conf`. Validate and reload:

```bash
sudo podman exec shared-nginx nginx -t
sudo podman exec shared-nginx nginx -s reload
```

## Verify

```bash
# Backend health (engine should report podman + a container count):
curl -s -u monitor:PASS http://10.3.5.99/monitoring/api/health
#   {"status":"ok","engine":"podman","containersVisible":9}

# Without credentials -> 401:
curl -si http://10.3.5.99/monitoring/api/health | head -n1
#   HTTP/1.1 401 Unauthorized

# Agent rollup + a container list + a stats snapshot:
curl -s -u monitor:PASS http://10.3.5.99/monitoring/api/agents
curl -s -u monitor:PASS "http://10.3.5.99/monitoring/api/containers?agent=compliance"
curl -s -u monitor:PASS "http://10.3.5.99/monitoring/api/stats?agent=compliance"

# A log tail and the SSE stream (Ctrl-C to stop):
curl -s -u monitor:PASS "http://10.3.5.99/monitoring/api/containers/compliance-backend/logs?tail=50"
curl -N -u monitor:PASS "http://10.3.5.99/monitoring/api/containers/compliance-backend/logs/stream?tail=20"

# UI:
#   http://10.3.5.99/monitoring   (browser prompts for basic-auth)
```

### Confirm the proxy is genuinely read-only

A write through the proxy must be rejected (POST=0). From inside the network:

```bash
# Should return 403 Forbidden (proxy blocks POST), never actually restart:
sudo podman exec monitoring-backend \
  python -c "import urllib.request as u; \
  print(u.urlopen(u.Request('http://socket-proxy:2375/containers/x/restart', method='POST')).status)"
```

## Notes

- No `ports:` here — nginx handles all external routing.
- No database/redis: this agent reads only from the Podman engine.
- Backend image is built locally and tagged `localhost/monitoring-backend:latest`
  with `pull_policy: never`.
- Engine access is **read-only by construction**: the backend issues only
  `containers.list`, `container.stats`, `container.logs`; the proxy rejects all
  writes with POST=0/EXEC=0.
- The backend runs as a non-root user inside the container.
