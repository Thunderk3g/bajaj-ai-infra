# SEO Agent

Independent AI agent deployment. Joins the shared stack (postgres + redis +
nginx) via the external `shared-network`. This agent is the recommended
**template** when adding a new agent (see `docs/new-agent-guide.md`).

| Component            | Container        | Container Port | Public Path     |
|----------------------|------------------|----------------|-----------------|
| Frontend             | `seo-frontend`   | 3002           | `/seo/`         |
| Backend (API)        | `seo-backend`    | 8001           | `/seo/api/`     |
| Database             | `seo_db`         | on shared-postgres | —           |

## Prerequisites

The shared stack must already be running:

```bash
cd /opt/shared
sudo podman-compose up -d
```

`seo_db` is created automatically by `shared/init-db.sh` on first postgres
start.

## Deploy

```bash
cd /opt/seo-agent
sudo cp .env.example .env
sudo nano .env                 # set POSTGRES_PASSWORD (must match shared/.env)
sudo podman-compose up -d
sudo podman exec shared-nginx nginx -s reload
```

## Verify

```bash
curl http://10.3.5.99/seo/
curl http://10.3.5.99/seo/api/docs
```

## Notes

- No `ports:` here — nginx handles all external routing.
- `DATABASE_URL` / `REDIS_URL` reference shared services by container name.
- Images are built locally and tagged `localhost/seo-*:latest`
  with `pull_policy: never`.
