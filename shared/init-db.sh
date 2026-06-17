#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/init-db.sh
# Runs once on first postgres start (mounted into docker-entrypoint-initdb.d).
# Creates one database per agent and enables the pgvector extension on each.
#
# To add a new agent's database, add a line: create_db "<agentname>_db"
# ──────────────────────────────────────────────────────────────────────────
set -e

# Create a dedicated login role (least privilege per agent). Idempotent.
# Usage: create_role <rolename> <password>
create_role() {
  local role=$1
  local pass=$2
  psql -U "$POSTGRES_USER" -tc \
    "SELECT 1 FROM pg_roles WHERE rolname = '$role'" \
    | grep -q 1 \
    || psql -U "$POSTGRES_USER" -c "CREATE ROLE $role LOGIN PASSWORD '$pass'"
  echo "Role $role ready"
}

# Create a database, enable pgvector, and (optionally) hand it to an owner role.
# Usage: create_db <dbname> [owner_role]
create_db() {
  local dbname=$1
  local owner=${2:-$POSTGRES_USER}
  psql -U "$POSTGRES_USER" -tc \
    "SELECT 1 FROM pg_database WHERE datname = '$dbname'" \
    | grep -q 1 \
    || psql -U "$POSTGRES_USER" -c "CREATE DATABASE $dbname OWNER $owner"
  # Extension must be created by a superuser; do it on the target DB.
  psql -U "$POSTGRES_USER" -d "$dbname" \
    -c "CREATE EXTENSION IF NOT EXISTS vector"
  # Make sure the owner role can use the schema and the new extension type.
  psql -U "$POSTGRES_USER" -c "GRANT ALL PRIVILEGES ON DATABASE $dbname TO $owner"
  psql -U "$POSTGRES_USER" -d "$dbname" -c "GRANT ALL ON SCHEMA public TO $owner"
  echo "Database $dbname ready (owner: $owner)"
}

# ── compliance-agent: dedicated role + db ──────────────────────────────────
create_role "compliance_user" "${COMPLIANCE_DB_PASSWORD:-compliance_pass}"
create_db   "compliance_db"   "compliance_user"

# ── seo-agent: dedicated role + db ─────────────────────────────────────────
create_role "seo_user" "${SEO_DB_PASSWORD:-seo_pass}"
create_db   "seo_db"   "seo_user"

# ── add new agents below ───────────────────────────────────────────────────
# create_role "hr_user" "${HR_DB_PASSWORD:-hr_pass}"
# create_db   "hr_db"   "hr_user"
# create_role "voice_user" "${VOICE_DB_PASSWORD:-voice_pass}"
# create_db   "voice_db"   "voice_user"
