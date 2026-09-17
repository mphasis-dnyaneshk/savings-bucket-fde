# Savings Bucket

Savings Bucket is a goal-oriented savings capability for digital banking. Customers can create logical savings goals, track progress, contribute and withdraw money, view transaction history, and configure recurring contributions.

The project follows the approved design in the documents under [`documents/`](documents/): Python/FastAPI microservices, PostgreSQL, an API Gateway boundary, OIDC/JWT authentication, and asynchronous recurring-contribution processing with EventBridge/SQS in AWS.

## Current development status

The R0 foundation scaffold is now implemented:

- Shared FastAPI application factory with liveness and readiness endpoints.
- Correlation ID response handling through `X-Correlation-ID`.
- Pydantic Settings configuration loaded from `.env`.
- Local customer identity and idempotency-key dependencies.
- Common error response shape and domain service entrypoints.
- PostgreSQL 16 Docker Compose service.
- Foundation SQL migration for buckets, transactions, and outbox events.
- Docker image definition and Pytest/Ruff development configuration.

The domain handlers are intentionally still placeholders and return `501 Not Implemented`. Bucket persistence, contribution and withdrawal workflows, real OIDC/JWT validation, EventBridge/SQS processing, Terraform, and the frontend are not implemented yet. The next phase is R1: bucket creation, listing, details, progress, and ownership checks.

## MVP scope

- Create and list customer-owned savings buckets.
- View balance, target amount, target date, remaining amount, and progress.
- Contribute money to a bucket.
- Withdraw money from a bucket allocation.
- View contribution and withdrawal history.
- Configure and execute recurring contributions.
- Protect every operation with authentication and bucket-level authorization.

Future AI recommendations are advisory only and are not part of the MVP money-movement path.

## Service architecture

| Service | Responsibility | Initial priority |
| --- | --- | --- |
| `bucket-service` | Create, list, and view buckets; calculate progress; own bucket allocation state | R1 |
| `contribution-service` | Start contributions, call the banking adapter, enforce idempotency, and manage outcomes | R2 |
| `withdrawal-service` | Validate available allocation, start withdrawals, and manage outcomes | R2 |
| `recurring-contribution-service` | Store schedules, create due executions, and retry safely | R4 |
| `notification-service` | Consume approved domain events and deliver notifications | R5 / optional |
| `banking-transaction-service` | Authoritative debit/credit boundary; use a mocked adapter locally | R2 |

The transaction-history capability may remain within `bucket-service` for the MVP. A future recommendation service must remain isolated from financial transaction execution.

## Target repository structure

```text
savings-bucket/
├── services/
│   ├── bucket-service/
│   ├── contribution-service/
│   ├── withdrawal-service/
│   ├── recurring-contribution-service/
│   └── notification-service/
├── shared/
│   ├── auth/
│   ├── errors/
│   ├── events/
│   ├── idempotency/
│   └── observability/
├── db/
│   ├── migrations/
│   └── seed/
├── infra/
│   └── terraform/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── contract/
│   └── e2e/
├── docker-compose.yml
├── .env.example
└── README.md
```

## Prerequisites

- Python 3.12.8.
- Docker Desktop with Docker Compose.
- Git Bash in the VS Code terminal.
- Git.

AWS CLI and Terraform are needed later for cloud infrastructure work, but are not required for the current local foundation.

Local development should use a mocked banking adapter and local dependencies. Do not connect local experiments to production accounts or production financial data.

## Start locally

From the repository root, run the Git Bash bootstrap script:

```bash
bash ./scripts/run-local.sh
```

The script creates `.venv` if needed, installs the project with development dependencies, and starts PostgreSQL. Start `bucket-service` with:

```bash
./.venv/Scripts/python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001
```

Start the other services manually when needed:

```bash
./.venv/Scripts/python.exe -m uvicorn services.contribution_service.main:app --reload --port 8002
./.venv/Scripts/python.exe -m uvicorn services.withdrawal_service.main:app --reload --port 8003
./.venv/Scripts/python.exe -m uvicorn services.recurring_contribution_service.main:app --reload --port 8004
./.venv/Scripts/python.exe -m uvicorn services.notification_service.main:app --reload --port 8005
```

Alternatively, build and run all five service containers:

```bash
docker compose up --build
```

Stop the containers with `docker compose down`. Add `-v` only when you want to remove the local PostgreSQL volume and its data.

### Local ports

| Service | Local port |
| --- | ---: |
| `bucket-service` | 8001 |
| `contribution-service` | 8002 |
| `withdrawal-service` | 8003 |
| `recurring-contribution-service` | 8004 |
| `notification-service` | 8005 |
| PostgreSQL | 5432 |

Each FastAPI service exposes `GET /health/live` and `GET /health/ready`. The notification service also exposes `GET /internal/status`.

## Database

Compose starts PostgreSQL with database `savings_bucket`, username `savings`, password `savings`, and host port `5432`. Apply the foundation migration after PostgreSQL is ready:

```bash
docker compose exec -T postgres psql -U savings -d savings_bucket < db/migrations/001_foundation.sql
```

The migration creates `buckets`, `bucket_transactions`, and `outbox_events`. The services currently expose database configuration but do not yet perform database reads or writes.

## Local configuration

Create a local `.env` from `.env.example`. Keep secrets out of source control.

```dotenv
APP_ENV=local
LOG_LEVEL=INFO
DATABASE_URL=postgresql+psycopg://savings:savings@localhost:5432/savings_bucket
JWT_ISSUER=http://localhost:8080/realms/savings-bucket
JWT_AUDIENCE=savings-bucket-local
BANKING_ADAPTER_MODE=mock
EVENT_BUS_MODE=local
SQS_MODE=local
```

The final configuration names must match the implementation. AWS environments should use Secrets Manager and KMS rather than committed credentials or plaintext secrets.

## API surface

The initial route contracts are registered, but domain handlers intentionally return `501 Not Implemented` until R1/R2:

| Method | Endpoint | Service |
| --- | --- | --- |
| `POST` | `/v1/buckets` | Bucket |
| `GET` | `/v1/buckets` | Bucket |
| `GET` | `/v1/buckets/{bucketId}` | Bucket |
| `POST` | `/v1/buckets/{bucketId}/contributions` | Contribution |
| `POST` | `/v1/buckets/{bucketId}/withdrawals` | Withdrawal |
| `GET` | `/v1/buckets/{bucketId}/transactions` | Bucket/history |
| `POST` | `/v1/buckets/{bucketId}/recurring-contributions` | Recurring contribution |
| `PATCH` | `/v1/buckets/{bucketId}/recurring-contributions/{id}` | Recurring contribution |

Contribution and withdrawal routes require an `Idempotency-Key`; domain routes require the current local customer identity dependency. These are scaffold dependencies and must be completed with OIDC/JWT validation before production use. A contribution or withdrawal must remain `PENDING` until the banking capability confirms the outcome. Only confirmed success may change the logical bucket allocation.

## Data and consistency rules

- Store money as `NUMERIC`/`DECIMAL`, never floating point.
- Store timestamps in UTC.
- Use PostgreSQL transactions, constraints, and optimistic or row-level locking.
- Keep `PENDING`, `SUCCESS`, `FAILED`, and `REVERSED` as distinct transaction states.
- Use a transactional outbox for domain events.
- Deduplicate repeated requests and events.
- Reconcile cases where the banking capability succeeds but local completion is uncertain.
- A bucket is a logical allocation, not a separate bank account.

The initial tables are `buckets`, `bucket_transactions`, `recurring_contributions`, `outbox_events`, and audit records.

## Verification

Check the running foundation:

```bash
curl http://localhost:8001/health/live
curl http://localhost:8001/health/ready
curl http://localhost:8005/internal/status
```

Run the automated checks from the repository root:

```bash
./.venv/Scripts/python.exe -m pytest
./.venv/Scripts/python.exe -m ruff check .
```

The current tests cover the shared health contract. The minimum future end-to-end scenario is:

```text
authenticate -> create bucket -> contribute -> verify progress -> withdraw
-> view history -> configure recurring contribution -> process scheduled execution
```

Also test invalid amounts, unauthorized bucket access, duplicate idempotency keys, concurrent updates, banking timeouts, retries, and dead-letter handling.

## Delivery sequence

1. **R0 Foundation:** service skeleton, authentication, database connectivity, API boundary, CI checks, and observability.
2. **R1 Goal MVP:** bucket creation, listing, details, progress, and ownership checks.
3. **R2 Money Movement:** mocked banking adapter, contribution, withdrawal, idempotency, explicit states, and reconciliation.
4. **R3 History:** transaction records, pagination, references, and auditability.
5. **R4 Recurring:** scheduling, durable queue processing, retries, and DLQ behavior.
6. **R5 Production Readiness:** notifications, security hardening, telemetry, backup, recovery, and smoke tests.
7. **R6 Future AI:** governed advisory recommendations, isolated from money movement.

## Source documents

- [`FDE_Discovery_Document.txt`](documents/FDE_Discovery_Document.txt)
- [`FDE_PRD_Document.txt`](documents/FDE_PRD_Document.txt)
- [`FDE_SDD_Document.txt`](documents/FDE_SDD_Document.txt)
- [`FDE_Technical_Implementation_Plan.txt`](documents/FDE_Technical_Implementation_Plan.txt)
- [`FDE_Product_Backlog_User_Stories.txt`](documents/FDE_Product_Backlog_User_Stories.txt)
- [`FDE_UX_User_Journey_Document.txt`](documents/FDE_UX_User_Journey_Document.txt)
