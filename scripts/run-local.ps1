$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

docker compose up -d postgres
docker compose exec -T postgres sh -c 'for migration in /migrations/*.sql; do psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -f "$migration"; done'
Write-Host "Foundation ready. Start a service with:"
Write-Host ".\.venv\Scripts\python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001"
