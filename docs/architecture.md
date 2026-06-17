# Architecture

The Bajaj AI Platform runs many independent AI agents on a single RHEL9 VM
using Podman. A single **shared stack** (postgres + redis + nginx) backs every
agent. Each agent is its own deployment that joins the shared bridge network.

## Topology

```
┌──────────────────────────────────────────────────────────────┐
│                     VM: 10.3.5.99                            │
│                                                              │
│  Browser ──► :80 ──► shared-nginx                           │
│                           │                                  │
│              ┌────────────┼────────────┐                     │
│              │            │            │                     │
│         /compliance/    /seo/       /hr/  ...                │
│              │            │            │                     │
│    compliance-frontend  seo-frontend  hr-frontend            │
│    compliance-backend   seo-backend   hr-backend             │
│              │            │            │                     │
│              └────────────┴────────────┘                     │
│                           │                                  │
│              ┌────────────┴────────────┐                     │
│              │                         │                     │
│      shared-postgres             shared-redis                │
│      (all agent DBs)             (all agent cache)           │
│                                                              │
│  ── all on shared-network (bridge) ──────────────────────── │
└──────────────────────────────────────────────────────────────┘
```

## Key principles

1. **One shared stack.** `shared/docker-compose.yml` runs ONLY
   `shared-postgres`, `shared-redis`, and `shared-nginx`. It owns the
   `shared-network` (bridge) and the named volumes `shared-pgdata` /
   `shared-redisdata`.

2. **Agents are independent.** Each agent has its own compose file containing
   ONLY its own `*-frontend` and `*-backend` containers. Agents declare
   `networks: shared-network: external: true` to join the existing network —
   they never recreate it.

3. **Nginx is the only ingress.** Only `shared-nginx` publishes a host port
   (`80:80`). Agents never set `ports:`. Nginx routes by path
   (`/compliance/`, `/seo/`, …) to the agent containers by name over
   `shared-network`.

4. **Postgres is multi-tenant by database.** `shared/init-db.sh` creates one
   database per agent (`compliance_db`, `seo_db`, …) and enables the `vector`
   (pgvector) extension on each.

5. **All images are local.** Every service uses a full `docker.io/...` image
   path (or a locally built `localhost/...:latest` image) with
   `pull_policy: never`. Base images are fetched ahead of time with
   `shared/scripts/pre-pull-images.sh`.

## Networking

| Name             | Type   | Owner                         |
|------------------|--------|-------------------------------|
| `shared-network` | bridge | `shared/docker-compose.yml`   |

Containers reach each other by container name:
`shared-postgres:5432`, `shared-redis:6379`, `compliance-backend:8000`, etc.

## Volumes

| Volume              | Mounted in        | Purpose            |
|---------------------|-------------------|--------------------|
| `shared-pgdata`     | `shared-postgres` | Postgres data dir  |
| `shared-redisdata`  | `shared-redis`    | Redis AOF data     |

## Startup order

1. `shared` stack comes up; nginx, postgres, redis become healthy.
2. Each agent comes up and connects to shared services by name.
3. Nginx is reloaded (`nginx -s reload`) to pick up any new routes.

`shared/scripts/start-all.sh` automates this exact order.
