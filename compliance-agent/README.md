# Compliance Agent

Independent AI agent deployment. Joins the shared stack (postgres + redis +
nginx) via the external `shared-network`.

| Component            | Container             | Container Port | Public Path           |
|----------------------|-----------------------|----------------|-----------------------|
| Frontend             | `compliance-frontend` | 3000           | `/compliance/`        |
| Backend (API)        | `compliance-backend`  | 8000           | `/compliance/api/`    |
| Database             | `compliance_db`       | on shared-postgres | —                 |

## Prerequisites

The shared stack must already be running:

```bash
cd /opt/shared
sudo podman-compose up -d
```

`compliance_db` is created automatically by `shared/init-db.sh` on first
postgres start.

## Deploy

```bash
cd /opt/compliance-agent
sudo cp .env.example .env
sudo nano .env                 # set POSTGRES_PASSWORD (must match shared/.env)
sudo podman-compose up -d

# routes already exist in nginx.conf; reload to be safe:
sudo podman exec shared-nginx nginx -s reload
```

## Verify

```bash
curl http://10.3.5.99/compliance/
curl http://10.3.5.99/compliance/api/docs
```

## Notes

- No `ports:` here — nginx handles all external routing.
- `DATABASE_URL` and `REDIS_URL` point at `shared-postgres` / `shared-redis`
  by container name over `shared-network`.
- Build is local: images are tagged `localhost/compliance-*:latest` with
  `pull_policy: never`.
