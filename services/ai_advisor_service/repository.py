from decimal import Decimal

import psycopg
from psycopg.rows import dict_row


def fetch_customer_snapshot(database_url: str, customer_id: str) -> dict:
    with psycopg.connect(database_url, row_factory=dict_row) as connection:
        buckets = connection.execute(
            """
            SELECT b.bucket_id, b.name, b.target_amount, b.current_balance,
                   b.target_date, b.status,
                   COALESCE(SUM(t.amount) FILTER (
                       WHERE t.status = 'SUCCESS' AND t.type = 'CONTRIBUTION'
                   ), 0) AS total_contributions,
                   COALESCE(SUM(t.amount) FILTER (
                       WHERE t.status = 'SUCCESS' AND t.type = 'WITHDRAWAL'
                   ), 0) AS total_withdrawals
            FROM buckets AS b
            LEFT JOIN bucket_transactions AS t
              ON t.bucket_id = b.bucket_id AND t.customer_id = b.customer_id
            WHERE b.customer_id = %s
            GROUP BY b.bucket_id
            ORDER BY b.created_at DESC
            """,
            (customer_id,),
        ).fetchall()
        monthly_activity = connection.execute(
            """
            SELECT TO_CHAR(date_trunc('month', created_at), 'YYYY-MM') AS month,
                   type,
                   COUNT(*) AS transaction_count,
                   SUM(amount) AS total_amount
            FROM bucket_transactions
            WHERE customer_id = %s
              AND status = 'SUCCESS'
              AND created_at >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY date_trunc('month', created_at), type
            ORDER BY date_trunc('month', created_at), type
            """,
            (customer_id,),
        ).fetchall()

    return {
        "buckets": [
            {
                **row,
                "bucket_id": str(row["bucket_id"]),
                "target_amount": str(row["target_amount"]),
                "current_balance": str(row["current_balance"]),
                "target_date": (
                    row["target_date"].isoformat() if row["target_date"] else None
                ),
                "total_contributions": str(row["total_contributions"]),
                "total_withdrawals": str(row["total_withdrawals"]),
                "remaining_amount": str(
                    max(
                        row["target_amount"] - row["current_balance"],
                        Decimal("0"),
                    )
                ),
            }
            for row in buckets
        ],
        "monthly_activity": [
            {
                "month": row["month"],
                "type": row["type"],
                "transaction_count": row["transaction_count"],
                "total_amount": str(row["total_amount"]),
            }
            for row in monthly_activity
        ],
    }
