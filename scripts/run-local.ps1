$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    py -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"

docker compose up -d postgres
Write-Host "Foundation ready. Start a service with:"
Write-Host ".\.venv\Scripts\python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001"
