#!/bin/bash
# ──────────────────────────────────────────────────────────────────────────
# shared/init-db.sh
# Runs once on first postgres start (mounted into docker-entrypoint-initdb.d).
# Creates one database per agent and enables the pgvector extension on each.
#
# To add a new agent's database, add a line: create_db "<agentname>_db"
# ──────────────────────────────────────────────────────────────────────────
set -e

create_db() {
  local dbname=$1
  psql -U "$POSTGRES_USER" -tc \
    "SELECT 1 FROM pg_database WHERE datname = '$dbname'" \
    | grep -q 1 \
    || psql -U "$POSTGRES_USER" -c "CREATE DATABASE $dbname"
  psql -U "$POSTGRES_USER" -d "$dbname" \
    -c "CREATE EXTENSION IF NOT EXISTS vector"
  echo "Database $dbname ready"
}

create_db "compliance_db"
create_db "seo_db"
# create_db "hr_db"         # uncomment when hr-agent is added
# create_db "voice_db"      # uncomment when voice-agent is added
