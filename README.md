# Savings Bucket

Savings Bucket is a goal-oriented savings capability for digital banking. Customers can create logical savings goals, track progress, contribute and withdraw money, view transaction history, and configure recurring contributions.

The project follows the approved design in the documents under [`documents/`](documents/): Python/FastAPI microservices, PostgreSQL, an API Gateway boundary, OIDC/JWT authentication, and asynchronous recurring-contribution processing with EventBridge/SQS in AWS.

## Current status

This repository currently contains the product, UX, system design, backlog, and implementation-plan documents. The application code and local runtime files have not been scaffolded yet. The instructions below define the local development target and the order in which to build it.

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

Install these before creating the service skeleton:

- Python and `pip` version selected by the team for the FastAPI services.
- Docker Desktop with Docker Compose.
- PostgreSQL client tools, or access to `psql` through a container.
- Git.
- AWS CLI and Terraform when developing against AWS infrastructure.

Local development should use a mocked banking adapter and local dependencies. Do not connect local experiments to production accounts or production financial data.

## Start locally

The repository does not yet contain `docker-compose.yml`, service directories, or dependency lock files. After the foundation scaffold is created, use this flow from the repository root:

```powershell
# Create and activate a local virtual environment for a service.
py -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies after the service requirements are added.
python -m pip install --upgrade pip
python -m pip install -r services\bucket-service\requirements.txt

# Start PostgreSQL and local messaging dependencies.
docker compose up -d postgres

# Apply versioned migrations and optional seed data.
alembic upgrade head
python -m db.seed

# Start the first service during R1 development.
uvicorn services.bucket_service.app:app --reload --port 8001
```

When the remaining services are implemented, start them in this order:

1. PostgreSQL and local messaging dependencies.
2. `bucket-service`.
3. The mocked `banking-transaction-service`.
4. `contribution-service` and `withdrawal-service`.
5. `recurring-contribution-service` and its scheduler/queue workers.
6. `notification-service`, if enabled.
7. The API Gateway or local web client.

The exact module paths, ports, and commands must be recorded here when the service skeleton is committed. The commands above are the intended development flow, not currently runnable commands.

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

The initial API contract is:

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

Money-changing requests must include a unique `Idempotency-Key`. A contribution or withdrawal must remain `PENDING` until the banking capability confirms the outcome. Only confirmed success may change the logical bucket allocation.

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

Run these checks as each service is added:

```powershell
# Replace with the repository's final test and lint commands.
python -m pytest
python -m ruff check .
python -m mypy .
```

The minimum end-to-end scenario is:

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
