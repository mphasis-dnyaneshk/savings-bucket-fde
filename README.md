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

The bucket, contribution, withdrawal, recurring-contribution, and notification services now expose working mock-first API flows. Contribution and withdrawal requests return deterministic mock `SUCCESS` records with idempotency protection. Recurring schedules support create, list, read, pause, and update. Notification delivery is represented by an in-memory `DELIVERED` result. The React + TypeScript + Vite frontend is now scaffolded and wired to these local APIs. Real OIDC/JWT validation, EventBridge/SQS processing, Terraform, and financial integration are not implemented yet.

## MVP scope

- Create and list customer-owned savings buckets. **Implemented in bucket-service.**
- View balance, target amount, target date, remaining amount, and progress. **Implemented in bucket-service.**
- Contribute money to a bucket. **Implemented as a mock contribution workflow.**
- Withdraw money from a bucket allocation. **Implemented as a mock withdrawal workflow.**
- View contribution and withdrawal status by ID. **Implemented in mock services.**
- Configure, list, read, pause, and update recurring contributions. **Implemented as mock schedule management.**
- Deliver and read notifications. **Implemented as an in-memory local notification flow.**
- Protect every operation with authentication and bucket-level authorization.

Future AI recommendations are advisory only and are not part of the MVP money-movement path.

## Service architecture

| Service | Responsibility | Initial priority |
| --- | --- | --- |
| `bucket-service` | Create, list, and view buckets; calculate progress; own bucket allocation state | R1 |
| `contribution-service` | Mock contribution records, idempotency, and status lookup | R2 mock slice |
| `withdrawal-service` | Mock withdrawal records, idempotency, and status lookup | R2 mock slice |
| `recurring-contribution-service` | Mock schedule create/list/read/update and status | R4 mock slice |
| `notification-service` | Mock notification delivery and customer-scoped lookup | R5 mock slice |
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
├── frontend/       React + TypeScript + Vite web application
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

## Frontend technology decision

The capstone frontend will use **React + TypeScript + Vite**. It will provide the responsive Savings Bucket web experience described in the UX document: dashboard, bucket detail, create bucket, add money, withdraw, transactions, and recurring contribution screens.

The frontend will call the FastAPI services through the documented API boundary and use local mock data or mock service responses during development. It must remain responsive, keyboard accessible, screen-reader friendly, and must not imply that a bucket is a separate bank account.

## Start the frontend

Start the backend services first on ports `8001` through `8005`, then run the frontend from the repository root:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

Open `http://localhost:5173`. The UI uses `customer-001` by default and sends it as the local `X-Customer-ID` header. Change `VITE_CUSTOMER_ID` in `frontend/.env` to simulate another local customer.

The frontend currently supports:

- Dashboard summary and goal cards.
- Create bucket flow.
- Bucket detail with progress and remaining amount.
- Mock contribution and withdrawal actions.
- Recurring contribution create, list, pause, and resume.
- Activity view and notification feedback.
- Responsive mobile, tablet, and desktop layouts.

Build the production bundle with:

```bash
npm run build
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

The normal local workflow uses your installed PostgreSQL. Alternatively, build and run PostgreSQL, all five backend services, and the frontend service with Docker Compose:

```bash
docker compose up --build
```

Open the containerized frontend at `http://localhost:5173`. The frontend container serves the Vite production build through Nginx, while the browser calls the backend services through their published ports `8001` through `8005`.

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
| `POST` | `/v1/buckets/{bucket_id}/contributions` | Mock contribution |
| `POST` | `/v1/buckets/{bucket_id}/withdrawals` | Mock withdrawal |
| `POST` | `/v1/buckets/{bucket_id}/recurring-contributions` | Mock recurring schedule |
| `PATCH` | `/v1/buckets/{bucket_id}/recurring-contributions/{id}` | Update mock schedule |

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

## Mock service APIs

All mock service data is held in memory and resets when that service restarts. These endpoints do not connect to production banking data.

### Contribution service (`localhost:8002`)

```bash
curl -X POST http://localhost:8002/v1/buckets/<bucket_id>/contributions \
	-H 'Content-Type: application/json' \
	-H 'X-Customer-ID: customer-001' \
	-H 'Idempotency-Key: contribution-001' \
	-d '{"amount":"100.00"}'
curl -H 'X-Customer-ID: customer-001' http://localhost:8002/v1/contributions/<contribution_id>
```

Repeating the same request with the same customer, bucket, amount, and idempotency key returns the original record. Reusing the key with different data returns `409`.

### Withdrawal service (`localhost:8003`)

```bash
curl -X POST http://localhost:8003/v1/buckets/<bucket_id>/withdrawals \
	-H 'Content-Type: application/json' \
	-H 'X-Customer-ID: customer-001' \
	-H 'Idempotency-Key: withdrawal-001' \
	-d '{"amount":"25.00"}'
curl -H 'X-Customer-ID: customer-001' http://localhost:8003/v1/withdrawals/<withdrawal_id>
```

The mock returns `SUCCESS`; real balance validation and banking integration are future work.

### Recurring contribution service (`localhost:8004`)

```bash
curl -X POST http://localhost:8004/v1/buckets/<bucket_id>/recurring-contributions \
	-H 'Content-Type: application/json' \
	-H 'X-Customer-ID: customer-001' \
	-d '{"amount":"100.00","frequency":"MONTHLY","start_date":"2026-10-01"}'
curl -H 'X-Customer-ID: customer-001' http://localhost:8004/v1/buckets/<bucket_id>/recurring-contributions
curl -X PATCH http://localhost:8004/v1/buckets/<bucket_id>/recurring-contributions/<schedule_id> \
	-H 'Content-Type: application/json' \
	-H 'X-Customer-ID: customer-001' \
	-d '{"status":"PAUSED"}'
curl -H 'X-Customer-ID: customer-001' http://localhost:8004/v1/recurring-contributions/<schedule_id>
```

Supported schedule states are `ACTIVE`, `PAUSED`, and `CANCELLED`. Scheduling and execution are currently mock-only.

### Notification service (`localhost:8005`)

```bash
curl -X POST http://localhost:8005/internal/notifications \
	-H 'Content-Type: application/json' \
	-d '{"customer_id":"customer-001","event_type":"ContributionCompleted","message":"Your contribution was completed."}'
curl -H 'X-Customer-ID: customer-001' http://localhost:8005/v1/notifications/<notification_id>
```

The local notification provider returns `DELIVERED` without sending an external message.

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

The tests cover the shared health contract, bucket lifecycle, customer isolation, contribution idempotency, withdrawal status, recurring schedule lifecycle, and notification lookup. The minimum future end-to-end scenario is:

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
