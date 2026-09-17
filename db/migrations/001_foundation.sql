CREATE TABLE IF NOT EXISTS buckets (
    bucket_id UUID PRIMARY KEY,
    customer_id VARCHAR(128) NOT NULL,
    name VARCHAR(200) NOT NULL,
    target_amount NUMERIC(19, 4) NOT NULL CHECK (target_amount > 0),
    current_balance NUMERIC(19, 4) NOT NULL DEFAULT 0 CHECK (current_balance >= 0),
    target_date DATE,
    status VARCHAR(32) NOT NULL DEFAULT 'ACTIVE',
    version BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_buckets_customer_id ON buckets (customer_id);

CREATE TABLE IF NOT EXISTS bucket_transactions (
    transaction_id UUID PRIMARY KEY,
    bucket_id UUID NOT NULL REFERENCES buckets(bucket_id),
    customer_id VARCHAR(128) NOT NULL,
    type VARCHAR(32) NOT NULL,
    amount NUMERIC(19, 4) NOT NULL CHECK (amount > 0),
    status VARCHAR(32) NOT NULL,
    external_reference VARCHAR(200),
    idempotency_key VARCHAR(200) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (customer_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_bucket_transactions_bucket_id
    ON bucket_transactions (bucket_id, created_at DESC);

CREATE TABLE IF NOT EXISTS outbox_events (
    event_id UUID PRIMARY KEY,
    aggregate_id UUID NOT NULL,
    event_type VARCHAR(128) NOT NULL,
    payload JSONB NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    published_at TIMESTAMPTZ
);
