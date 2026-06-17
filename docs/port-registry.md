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
| hr-agent         | hr-frontend:3004         | hr-backend:8002         | /hr/           | reserved |
| voice-agent      | voice-frontend:3006      | voice-backend:8003      | /voice/        | reserved |
| (next)           | <name>-frontend:3008     | <name>-backend:8004     | /<name>/       | free     |

## Allocation rules

- **Frontend ports:** 3000, 3002, 3004, 3006, 3008, … (step 2)
- **Backend ports:** 8000, 8001, 8002, 8003, 8004, … (step 1)
- **Host ports:** none for agents — only `shared-nginx` binds `80:80`.
- Container ports only need to be unique enough to be unambiguous; nginx
  routes by container name + port, so collisions across containers are fine in
  practice, but keeping them unique avoids confusion.

## Databases

Each agent gets one database on `shared-postgres`, named `<agent>_db` with the
`vector` extension enabled (see `shared/init-db.sh`).

| Agent            | Database        | Status   |
|------------------|-----------------|----------|
| compliance-agent | compliance_db   | active   |
| seo-agent        | seo_db          | active   |
| hr-agent         | hr_db           | reserved |
| voice-agent      | voice_db        | reserved |
