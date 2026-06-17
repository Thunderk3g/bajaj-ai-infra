# Adding a New Agent

Follow these steps to add a new agent (e.g. `hr-agent`) to the platform.
Use `seo-agent/` as the template — it is the simplest complete example.

## Step 1 — Check the port registry

Open [`docs/port-registry.md`](port-registry.md) and pick the next available
frontend and backend ports.

## Step 2 — Create the agent folder in the repo

```bash
cp -r seo-agent/ <agentname>-agent/      # use SEO as the template
```

## Step 3 — Write docker-compose.yml

In `<agentname>-agent/docker-compose.yml`:

- Replace every `seo` with `<agentname>`.
- Update the container ports (frontend/backend) to your chosen values.
- Update the `DATABASE_URL` database name to `<agentname>_db`.
- Keep this block exactly — **never remove it**:

  ```yaml
  networks:
    shared-network:
      external: true
  ```

- Do NOT add `ports:`. Do NOT add postgres/redis here.

## Step 4 — Add the database to shared/init-db.sh

Add (or uncomment) a line in `shared/init-db.sh`:

```bash
create_db "<agentname>_db"
```

> Note: `init-db.sh` only runs on the *first* postgres start. If postgres is
> already initialized, create the database manually:
>
> ```bash
> sudo podman exec -it shared-postgres psql -U postgres \
>   -c "CREATE DATABASE <agentname>_db;"
> sudo podman exec -it shared-postgres psql -U postgres -d <agentname>_db \
>   -c "CREATE EXTENSION IF NOT EXISTS vector;"
> ```

## Step 5 — Add nginx routes to shared/nginx.conf

```bash
cd /opt/shared
./scripts/add-agent-route.sh <agentname> <fe-port> <be-port>
```

…or add the `upstream` + `location` blocks manually between the
`BEGIN/END UPSTREAMS` and `BEGIN/END LOCATIONS` markers in `nginx.conf`.

## Step 6 — Update the port registry

Record your new ports and path in [`docs/port-registry.md`](port-registry.md).

## Step 7 — Commit and push

```bash
git add .
git commit -m "feat: add <agentname>"
git push
```

## Step 8 — Pull and deploy on the VM

```bash
cd /opt/shared
sudo git pull

cd /opt/<agentname>-agent
sudo cp .env.example .env       # set POSTGRES_PASSWORD
sudo podman-compose up -d

sudo podman exec shared-nginx nginx -s reload
```

## Step 9 — Verify

```bash
curl http://10.3.5.99/<agentname>/
curl http://10.3.5.99/<agentname>/api/docs
```

## Checklist

- [ ] Ports chosen from the registry (no collisions)
- [ ] `docker-compose.yml` has ONLY this agent's containers
- [ ] `networks: shared-network: external: true` present
- [ ] No `ports:` on agent containers
- [ ] `<agentname>_db` created (init-db.sh or manual)
- [ ] nginx routes added and `nginx -t` passes
- [ ] port-registry.md updated
- [ ] endpoints return 200
