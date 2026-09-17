FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY shared ./shared
COPY services ./services

RUN pip install --no-cache-dir --upgrade pip \\
    && pip install --no-cache-dir ".[dev]"

ARG SERVICE_MODULE=services.bucket_service.main
ENV SERVICE_MODULE=${SERVICE_MODULE}
ENV PYTHONUNBUFFERED=1

CMD ["sh", "-c", "uvicorn ${SERVICE_MODULE}:app --host 0.0.0.0 --port 8000"]
