# Savings Bucket: Current Architecture and User Flow

This diagram reflects the implemented local mock-first flow in the repository. It does not represent the planned production API Gateway, OIDC/JWT, banking, EventBridge, or SQS components.

## Current local architecture

```mermaid
flowchart LR
    customer([Customer])
    browser[React + TypeScript + Vite<br/>Browser UI<br/>customer-001]

    subgraph compose[Docker Compose local environment]
        bucket[Bucket service<br/>FastAPI :8001<br/>Buckets + allocation state]
        contribution[Contribution service<br/>FastAPI :8002<br/>Mock contribution records]
        withdrawal[Withdrawal service<br/>FastAPI :8003<br/>Mock withdrawal records]
        recurring[Recurring contribution service<br/>FastAPI :8004<br/>Mock schedules]
        notification[Notification service<br/>FastAPI :8005<br/>In-memory notifications]
        postgres[(PostgreSQL 16<br/>savings_bucket<br/>:5432)]
    end

    customer --> browser
    browser -->|GET/POST /v1/buckets<br/>GET transactions| bucket
    browser -->|POST/GET /v1/buckets/:bucket_id/contributions| contribution
    browser -->|POST/GET /v1/buckets/:bucket_id/withdrawals| withdrawal
    browser -->|POST/GET/PATCH recurring-contributions| recurring
    browser -->|GET/DELETE notifications\nPOST internal notification| notification

    contribution -.->|POST /internal/buckets/:bucket_id/transactions| bucket
    withdrawal -.->|POST /internal/buckets/:bucket_id/transactions| bucket

    bucket -->|PostgresBucketStore<br/>when DATABASE_URL is configured| postgres
    bucket -.->|InMemoryBucketStore<br/>when DATABASE_URL is absent| bucketMemory[(Process memory)]
    contribution --> contributionMemory[(Process memory)]
    withdrawal --> withdrawalMemory[(Process memory)]
    recurring --> recurringMemory[(Process memory)]
    notification --> notificationMemory[(Process memory)]

    classDef user fill:#f4efe6,stroke:#a56b2b,color:#2f241a,stroke-width:2px
    classDef service fill:#e7f2ef,stroke:#23766b,color:#163c37,stroke-width:1.5px
    classDef data fill:#fff7d6,stroke:#b58a22,color:#4a3b08,stroke-width:1.5px
    classDef future fill:#eeeeee,stroke:#999999,color:#555555
    class customer,browser user
    class bucket,contribution,withdrawal,recurring,notification service
    class postgres,bucketMemory,contributionMemory,withdrawalMemory,recurringMemory,notificationMemory data
```

## User flow: create and inspect a goal

```mermaid
sequenceDiagram
    actor Customer
    participant UI as React browser UI
    participant B as bucket-service :8001
    participant DB as PostgreSQL or in-memory bucket store
    participant R as recurring-contribution-service :8004

    Customer->>UI: Open dashboard
    UI->>B: GET /v1/buckets\nX-Customer-ID: customer-001
    B->>DB: List customer-owned buckets
    DB-->>B: Buckets with balance and progress
    B-->>UI: Bucket list
    Customer->>UI: Create goal
    UI->>B: POST /v1/buckets
    B->>DB: Create bucket allocation
    DB-->>B: New bucket
    B-->>UI: 201 BucketResponse
    UI->>B: GET /v1/buckets/{id}/transactions
    UI->>R: GET /v1/buckets/{id}/recurring-contributions
    B-->>UI: Transaction history
    R-->>UI: Schedule list
    UI-->>Customer: Goal detail view
```

## User flow: contribution or withdrawal

```mermaid
sequenceDiagram
    actor Customer
    participant UI as React browser UI
    participant M as contribution-service or withdrawal-service
    participant B as bucket-service :8001
    participant DB as Bucket store
    participant N as notification-service :8005

    Customer->>UI: Submit amount
    UI->>M: POST money-movement endpoint\nX-Customer-ID + Idempotency-Key
    M->>M: Create or reuse mock record
    M->>B: POST /internal/buckets/{id}/transactions
    B->>DB: Apply transaction\nvalidate ownership, balance, idempotency
    DB-->>B: Updated balance and transaction
    B-->>M: Updated bucket response
    M-->>UI: ContributionResponse or WithdrawalResponse
    UI->>N: POST /internal/notifications
    N->>N: Store delivered notification in memory
    N-->>UI: NotificationResponse
    UI->>B: Reload buckets and transactions
    B-->>UI: Updated balance and activity
    UI-->>Customer: Status message and refreshed goal
```

## User flow: recurring contributions and notifications

```mermaid
flowchart TD
    user([Customer]) --> ui[React UI]
    ui -->|Create, list, pause, resume| recurring[Recurring contribution service]
    recurring --> recurringStore[(In-memory schedule store)]
    recurring -->|ScheduleResponse| ui

    ui -->|List notifications| notification[Notification service]
    notification --> notificationStore[(In-memory notification store)]
    notificationStore --> notification
    notification -->|NotificationResponse list| ui
    ui -->|Dismiss notification| notification

    note[Current limitation:\nrecurring schedules do not trigger a background\ncontribution processor yet]
    recurring -.-> note
```

## Implemented versus planned

| Area | Current local behavior | Planned production boundary |
| --- | --- | --- |
| Identity | `X-Customer-ID` header | OIDC/JWT validation |
| Client routing | Browser calls each service directly | API Gateway boundary |
| Money movement | Mock records and mock banking mode | Banking transaction service and provider adapter |
| Bucket persistence | PostgreSQL when configured, otherwise memory | Durable service-owned persistence |
| Other service records | In-memory stores | Durable stores and event-driven processing |
| Recurring execution | Schedule CRUD only | EventBridge/SQS worker flow |
| Notifications | Local delivered result in memory | Notification delivery provider |