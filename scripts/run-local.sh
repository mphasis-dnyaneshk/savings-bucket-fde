#!/usr/bin/env bash
set -euo pipefail

if [[ ! -d ".venv" ]]; then
  python -m venv .venv
fi

./.venv/Scripts/python.exe -m pip install --upgrade pip
./.venv/Scripts/python.exe -m pip install -e ".[dev]"

docker compose up -d postgres

echo "Foundation ready. Start a service with:"
echo "./.venv/Scripts/python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001"
