# Services

Each directory is an independently deployable FastAPI service. The foundation exposes health endpoints and API placeholders only; implement domain behavior in the service that owns the corresponding state.

| Service | Local port |
| --- | ---: |
| bucket-service | 8001 |
| contribution-service | 8002 |
| withdrawal-service | 8003 |
| recurring-contribution-service | 8004 |
| notification-service | 8005 |
