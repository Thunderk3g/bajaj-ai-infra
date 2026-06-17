# Bajaj AI Platform

Multi-agent AI infrastructure running on a single RHEL9 VM with Podman.

## Architecture

One shared stack (postgres + redis + nginx) serves all AI agents.
Each agent is an independent deployment that joins the shared network.

> This repository mirrors the `/opt/` directory on the VM **exactly**.
> When cloned into `/opt/`, every file lands in the right place immediately.

```
/opt/
├── shared/              ← shared-postgres, shared-redis, shared-nginx
├── compliance-agent/    ← compliance-frontend, compliance-backend
├── seo-agent/           ← seo-frontend, seo-backend
└── docs/
```

## Quick Start (on VM)

```bash
cd /opt
sudo git clone https://github.com/YOUR_ORG/bajaj-ai-platform.git .

cd shared
sudo cp .env.example .env
sudo nano .env                        # set POSTGRES_PASSWORD
# copy CA certs to shared/certs/
sudo bash scripts/pre-pull-images.sh
sudo podman-compose up -d
curl http://localhost/health           # should return OK
```

## Deploy an Agent

```bash
cd /opt/compliance-agent
sudo podman-compose up -d
curl http://localhost/compliance/
```

## Add a New Agent

See [docs/new-agent-guide.md](docs/new-agent-guide.md).

## Active Agents

| Agent      | URL                              | Status   |
|------------|----------------------------------|----------|
| Compliance | http://10.3.5.99/compliance/     | active   |
| SEO        | http://10.3.5.99/seo/            | active   |

## Constraints

- `shared/docker-compose.yml`: ONLY postgres, redis, nginx — nothing else
- Each agent `docker-compose.yml`: ONLY that agent's containers
- Every agent MUST use `networks: shared-network: external: true`
- Never add `ports:` to agent containers (nginx handles routing)
- Never create postgres or redis in agent compose files
- All images: `pull_policy: never` and full `docker.io` paths
- Nginx reload command (not restart):

  ```bash
  sudo podman exec shared-nginx nginx -s reload
  ```

## Helper Scripts

All live in `shared/scripts/`:

| Script                | Purpose                                            |
|-----------------------|----------------------------------------------------|
| `pre-pull-images.sh`  | Pull all base images before first start            |
| `start-all.sh`        | Start shared stack, then every agent, reload nginx |
| `stop-all.sh`         | Stop all agents, then the shared stack             |
| `add-agent-route.sh`  | Add nginx upstream + location for a new agent       |
| `check-health.sh`     | Probe `/health` and each agent endpoint            |
