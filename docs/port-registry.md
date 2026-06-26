# Port Registry

Authoritative list of container ports and nginx paths for every agent.
**Always pick the next free ports here before adding a new agent**, then update
this table.

Frontends use even ports starting at 3000 (step 2); backends start at 8000
(step 1). Nothing is published on the host except nginx `:80`.

| Agent            | Container Frontend       | Container Backend       | Nginx Path     | Status   |
|------------------|--------------------------|-------------------------|----------------|----------|
| compliance-agent | compliance-frontend:3000 | compliance-backend:8000 | /compliance/   | active   |
| seo-agent        | seo-frontend:3002        | seo-backend:8001        | /seo/          | active   |
| monitoring-agent | (landing-frontend:80)¹   | monitoring-backend:8002 | /monitoring/   | active   |
| hr-agent         | hr-frontend:3004         | hr-backend:8003         | /hr/           | reserved |
| voice-agent      | voice-frontend:3006      | voice-backend:8004      | /voice/        | reserved |
| (next)           | <name>-frontend:3008     | <name>-backend:8005     | /<name>/       | free     |

> ¹ monitoring-agent has **no frontend container** — its UI ships as a route
> inside the existing `landing-frontend` SPA. It also runs a second container,
> `socket-proxy` (`ghcr.io/tecnativa/docker-socket-proxy`, internal :2375, no
> public route), a GET-only proxy in front of the rootful Podman socket.
> Backend port 8002 was previously pencilled in for hr-agent; per the agent
> monitoring design spec it is now monitoring's, and the hr/voice reservations
> shifted up one (8003/8004).

## Allocation rules

- **Frontend ports:** 3000, 3002, 3004, 3006, 3008, … (step 2)
- **Backend ports:** 8000, 8001, 8002, 8003, 8004, … (step 1)
- **Host ports:** none for agents — only `shared-nginx` binds `80:80`.
- Container ports only need to be unique enough to be unambiguous; nginx
  routes by container name + port, so collisions across containers are fine in
  practice, but keeping them unique avoids confusion.

## Databases

Each agent gets one database on `shared-postgres`, named `<agent>_db`, owned by
a dedicated least-privilege login role `<agent>_user`, with the `vector`
extension enabled (see `shared/init-db.sh`). Role passwords come from
`shared/.env` (`<AGENT>_DB_PASSWORD`) and must match each agent's own `.env`.

| Agent            | Database        | DB role          | Status   |
|------------------|-----------------|------------------|----------|
| compliance-agent | compliance_db   | compliance_user  | active   |
| seo-agent        | seo_db          | seo_user         | active   |
| hr-agent         | hr_db           | hr_user          | reserved |
| voice-agent      | voice_db        | voice_user       | reserved |
