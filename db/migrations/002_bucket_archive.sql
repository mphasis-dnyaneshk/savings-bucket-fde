ALTER TABLE buckets
    ADD COLUMN IF NOT EXISTS reached_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS archived_at TIMESTAMPTZ;

WITH balance_history AS (
    SELECT
        tx.bucket_id,
        tx.created_at,
        SUM(
            CASE
                WHEN tx.type = 'CONTRIBUTION' THEN tx.amount
                ELSE -tx.amount
            END
        ) OVER (
            PARTITION BY tx.bucket_id
            ORDER BY tx.created_at, tx.transaction_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS balance_after_transaction
    FROM bucket_transactions AS tx
    WHERE tx.status = 'SUCCESS'
), first_reached AS (
    SELECT
        history.bucket_id,
        MIN(history.created_at) FILTER (
            WHERE history.balance_after_transaction >= bucket.target_amount
        ) AS reached_at
    FROM balance_history AS history
    JOIN buckets AS bucket ON bucket.bucket_id = history.bucket_id
    GROUP BY history.bucket_id
)
UPDATE buckets AS bucket
SET reached_at = first_reached.reached_at
FROM first_reached
WHERE bucket.bucket_id = first_reached.bucket_id
  AND bucket.reached_at IS NULL
  AND first_reached.reached_at IS NOT NULL;

UPDATE buckets
SET reached_at = updated_at
WHERE reached_at IS NULL
    AND (status = 'REACHED' OR current_balance >= target_amount);

CREATE INDEX IF NOT EXISTS ix_buckets_customer_archived
    ON buckets (customer_id, status, archived_at DESC);