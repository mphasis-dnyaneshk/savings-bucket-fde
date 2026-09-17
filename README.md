# Savings Bucket

Savings Bucket is a goal-oriented savings capability for digital banking. Customers can create logical savings goals, track progress, contribute and withdraw money, view transaction history, and configure recurring contributions.

The project follows the approved design in the documents under [`documents/`](documents/): Python/FastAPI microservices, PostgreSQL, an API Gateway boundary, OIDC/JWT authentication, and asynchronous recurring-contribution processing with EventBridge/SQS in AWS.

## Current development status

The R0 foundation and the bucket-service R1 slice are implemented:

- Shared FastAPI application factory with liveness and readiness endpoints.
- Correlation ID response handling through `X-Correlation-ID`.
- Pydantic Settings configuration loaded from `.env`.
- Local customer identity and idempotency-key dependencies.
- Common error response shape and domain service entrypoints.
- Local PostgreSQL development workflow using the `dnyanesh_kudale` user.
- Mock/in-memory bucket store for development without production or database data.
- Optional PostgreSQL 16 Docker Compose service for isolated container development.
- Foundation SQL migration for buckets, transactions, and outbox events.
- Docker image definition and Pytest/Ruff development configuration.

The bucket service is now end-to-end for its current API surface: create, list, details, progress, and transaction-history reads. It supports a local `X-Customer-ID` identity header and filters every read by customer ownership. Contribution, withdrawal, recurring-contribution, real OIDC/JWT validation, EventBridge/SQS processing, Terraform, and the frontend are not implemented yet.

## MVP scope

- Create and list customer-owned savings buckets. **Implemented in bucket-service.**
- View balance, target amount, target date, remaining amount, and progress. **Implemented in bucket-service.**
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

Local development defaults to mock mode, which stores bucket data in memory and requires no production data or database credentials. PostgreSQL mode is also supported with database user `dnyanesh_kudale`; its password is read from `FDE_DB_PASS` and is never committed to the repository. Do not connect local experiments to production accounts or production financial data.

## Start locally

### Mock mode: fastest local start

Mock mode is the recommended capstone workflow for developing and demonstrating bucket-service. It uses the in-memory store when `FDE_DB_PASS` and `DATABASE_URL` are not set:

```bash
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
./.venv/Scripts/python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001
```

For a fresh checkout, create the environment first:

```bash
python -m venv .venv
./.venv/Scripts/python.exe -m pip install -e ".[dev]"
```

### PostgreSQL mode: local persistence

Use this mode when you want bucket data persisted in your installed PostgreSQL:

```bash
export FDE_DB_PASS='your-local-postgres-password'
bash ./scripts/run-local.sh
./.venv/Scripts/python.exe -m uvicorn services.bucket_service.main:app --reload --port 8001
```

The script verifies `psql`, creates `savings_bucket` if needed, applies the foundation migration, and starts no application process by itself. Start `bucket-service` with:

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

The normal local workflow uses your installed PostgreSQL. Alternatively, build and run all five service containers with the Compose PostgreSQL instance:

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

The local Git Bash workflow connects to PostgreSQL at `localhost:5432` with database `savings_bucket` and username `dnyanesh_kudale`. The script uses `FDE_DB_PASS` through `PGPASSWORD` for database creation and migration, then application settings use the same password to build `DATABASE_URL`.

For the optional Compose workflow, PostgreSQL uses database `savings_bucket`, username `savings`, password `savings`, and host port `5432`. Apply the foundation migration after the container is ready:

```bash
docker compose exec -T postgres psql -U savings -d savings_bucket < db/migrations/001_foundation.sql
```

The migration creates `buckets`, `bucket_transactions`, and `outbox_events`. Bucket-service reads and writes `buckets` in PostgreSQL mode. Mock mode does not require PostgreSQL and its data is reset whenever the process restarts.

## Local configuration

Create a local `.env` from `.env.example` if you need overrides. Keep secrets out of source control. The preferred Git Bash setup is to export `FDE_DB_PASS` in the terminal session.

```dotenv
APP_ENV=local
LOG_LEVEL=INFO
FDE_DB_PASS=
JWT_ISSUER=http://localhost:8080/realms/savings-bucket
JWT_AUDIENCE=savings-bucket-local
BANKING_ADAPTER_MODE=mock
EVENT_BUS_MODE=local
SQS_MODE=local
```

The final configuration names must match the implementation. AWS environments should use Secrets Manager and KMS rather than committed credentials or plaintext secrets.

## Bucket-service API

The following bucket-service APIs are implemented. Use `X-Customer-ID` as the temporary local identity header; replace it with OIDC/JWT authentication before production use:

| Method | Endpoint | Service |
| --- | --- | --- |
| `POST` | `/v1/buckets` | Create a bucket |
| `GET` | `/v1/buckets` | List the customer's buckets |
| `GET` | `/v1/buckets/{bucket_id}` | Get bucket details and progress |
| `GET` | `/v1/buckets/{bucket_id}/transactions` | List bucket transactions |
| `POST` | `/v1/buckets/{bucket_id}/contributions` | Planned contribution endpoint |
| `POST` | `/v1/buckets/{bucket_id}/withdrawals` | Planned withdrawal endpoint |
| `POST` | `/v1/buckets/{bucket_id}/recurring-contributions` | Planned recurring endpoint |
| `PATCH` | `/v1/buckets/{bucket_id}/recurring-contributions/{id}` | Planned recurring endpoint |

### Bucket API example

Create a bucket:

```bash
curl -X POST http://localhost:8001/v1/buckets \
	-H 'Content-Type: application/json' \
	-H 'X-Customer-ID: customer-001' \
	-d '{"name":"Emergency Fund","target_amount":"100000.00","target_date":"2027-12-31"}'
```

Copy the returned `bucket_id`, then list and inspect the bucket:

```bash
curl -H 'X-Customer-ID: customer-001' http://localhost:8001/v1/buckets
curl -H 'X-Customer-ID: customer-001' http://localhost:8001/v1/buckets/<bucket_id>
curl -H 'X-Customer-ID: customer-001' http://localhost:8001/v1/buckets/<bucket_id>/transactions
```

The response includes `current_balance`, `remaining_amount`, and `progress_percentage`. A different customer ID cannot access the bucket and receives `404 Bucket not found.`

Invalid or missing `X-Customer-ID` returns `401`. Invalid names, amounts, and dates are rejected by the request schema with `422`.

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
