#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".venv" ]]; then
  python -m venv .venv
fi

if [[ -z "${FDE_DB_PASS:-}" ]]; then
  echo "FDE_DB_PASS must be set before starting local development." >&2
  echo "Example: export FDE_DB_PASS='your-local-postgres-password'" >&2
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql was not found. Add the PostgreSQL bin directory to your Git Bash PATH." >&2
  exit 1
fi

./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

export PGPASSWORD="$FDE_DB_PASS"
if ! psql -h localhost -U dnyanesh_kudale -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname = 'savings_bucket'" | grep -q 1; then
  createdb -h localhost -U dnyanesh_kudale savings_bucket
fi

psql -h localhost -U dnyanesh_kudale -d savings_bucket -f db/migrations/001_foundation.sql

echo "Foundation ready. Start a service with:"
echo "FDE_DB_PASS is configured for local PostgreSQL at localhost:5432."
echo "./.venv/Scripts/python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001"
