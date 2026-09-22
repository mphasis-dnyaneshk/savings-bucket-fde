from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row


@dataclass(frozen=True)
class BucketRecord:
    bucket_id: UUID
    customer_id: str
    name: str
    target_amount: Decimal
    current_balance: Decimal
    target_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: UUID
    bucket_id: UUID
    customer_id: str
    type: str
    amount: Decimal
    status: str
    external_reference: str | None
    created_at: datetime


class BucketStore(Protocol):
    def create_bucket(
        self,
        customer_id: str,
        name: str,
        target_amount: Decimal,
        target_date: date | None,
    ) -> BucketRecord: ...

    def list_buckets(self, customer_id: str) -> list[BucketRecord]: ...

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None: ...

    def list_transactions(
        self, customer_id: str, bucket_id: UUID
    ) -> list[TransactionRecord]: ...

    def apply_transaction(
        self,
        customer_id: str,
        bucket_id: UUID,
        transaction_type: str,
        amount: Decimal,
        status: str,
        external_reference: str | None,
        idempotency_key: str,
    ) -> BucketRecord: ...


class InMemoryBucketStore:
    def __init__(self) -> None:
        self._buckets: dict[UUID, BucketRecord] = {}
        self._transactions: list[TransactionRecord] = []

    def create_bucket(
        self,
        customer_id: str,
        name: str,
        target_amount: Decimal,
        target_date: date | None,
    ) -> BucketRecord:
        now = datetime.now(timezone.utc)
        record = BucketRecord(
            bucket_id=uuid4(),
            customer_id=customer_id,
            name=name,
            target_amount=target_amount,
            current_balance=Decimal("0"),
            target_date=target_date,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        self._buckets[record.bucket_id] = record
        return record

    def list_buckets(self, customer_id: str) -> list[BucketRecord]:
        return sorted(
            (
                bucket
                for bucket in self._buckets.values()
                if bucket.customer_id == customer_id
            ),
            key=lambda bucket: bucket.created_at,
            reverse=True,
        )

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        bucket = self._buckets.get(bucket_id)
        return bucket if bucket and bucket.customer_id == customer_id else None

    def list_transactions(
        self, customer_id: str, bucket_id: UUID
    ) -> list[TransactionRecord]:
        return [
            transaction
            for transaction in self._transactions
            if transaction.customer_id == customer_id
            and transaction.bucket_id == bucket_id
        ]

    def apply_transaction(
        self,
        customer_id: str,
        bucket_id: UUID,
        transaction_type: str,
        amount: Decimal,
        status: str,
        external_reference: str | None,
        idempotency_key: str,
    ) -> BucketRecord:
        bucket = self.get_bucket(customer_id, bucket_id)
        if bucket is None:
            raise LookupError("Bucket not found.")
        if any(
            transaction.customer_id == customer_id
            and transaction.bucket_id == bucket_id
            and transaction.external_reference == external_reference
            for transaction in self._transactions
        ):
            return bucket
        if status == "SUCCESS":
            balance = (
                bucket.current_balance + amount
                if transaction_type == "CONTRIBUTION"
                else bucket.current_balance - amount
            )
            if balance < 0:
                raise ValueError("Withdrawal exceeds available bucket balance.")
        else:
            balance = bucket.current_balance
        now = datetime.now(timezone.utc)
        updated = BucketRecord(
            **{**bucket.__dict__, "current_balance": balance, "updated_at": now}
        )
        self._buckets[bucket_id] = updated
        self._transactions.append(
            TransactionRecord(
                transaction_id=uuid4(),
                bucket_id=bucket_id,
                customer_id=customer_id,
                type=transaction_type,
                amount=amount,
                status=status,
                external_reference=external_reference,
                created_at=now,
            )
        )
        return updated


class PostgresBucketStore:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

    def create_bucket(
        self,
        customer_id: str,
        name: str,
        target_amount: Decimal,
        target_date: date | None,
    ) -> BucketRecord:
        bucket_id = uuid4()
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                INSERT INTO buckets (bucket_id, customer_id, name, target_amount, target_date)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                          target_date, status, created_at, updated_at
                """,
                (bucket_id, customer_id, name, target_amount, target_date),
            ).fetchone()
        return _bucket_from_row(row)

    def list_buckets(self, customer_id: str) -> list[BucketRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT bucket_id, customer_id, name, target_amount, current_balance,
                       target_date, status, created_at, updated_at
                FROM buckets
                WHERE customer_id = %s
                ORDER BY created_at DESC
                """,
                (customer_id,),
            ).fetchall()
        return [_bucket_from_row(row) for row in rows]

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT bucket_id, customer_id, name, target_amount, current_balance,
                       target_date, status, created_at, updated_at
                FROM buckets
                WHERE bucket_id = %s AND customer_id = %s
                """,
                (bucket_id, customer_id),
            ).fetchone()
        return _bucket_from_row(row) if row else None

    def list_transactions(
        self, customer_id: str, bucket_id: UUID
    ) -> list[TransactionRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT transaction_id, bucket_id, customer_id, type, amount, status,
                       external_reference, created_at
                FROM bucket_transactions
                WHERE bucket_id = %s AND customer_id = %s
                ORDER BY created_at DESC
                """,
                (bucket_id, customer_id),
            ).fetchall()
        return [_transaction_from_row(row) for row in rows]

    def apply_transaction(
        self,
        customer_id: str,
        bucket_id: UUID,
        transaction_type: str,
        amount: Decimal,
        status: str,
        external_reference: str | None,
        idempotency_key: str,
    ) -> BucketRecord:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT bucket_id, customer_id, name, target_amount, current_balance,
                           target_date, status, created_at, updated_at
                    FROM buckets WHERE bucket_id = %s AND customer_id = %s FOR UPDATE
                    """,
                    (bucket_id, customer_id),
                ).fetchone()
                if not row:
                    raise LookupError("Bucket not found.")
                existing = connection.execute(
                    """
                    SELECT transaction_id FROM bucket_transactions
                    WHERE customer_id = %s AND idempotency_key = %s
                    """,
                    (customer_id, idempotency_key),
                ).fetchone()
                if existing:
                    return _bucket_from_row(row)
                current_balance = row["current_balance"]
                if status == "SUCCESS":
                    current_balance = (
                        current_balance + amount
                        if transaction_type == "CONTRIBUTION"
                        else current_balance - amount
                    )
                    if current_balance < 0:
                        raise ValueError("Withdrawal exceeds available bucket balance.")
                    row = connection.execute(
                        """
                        UPDATE buckets SET current_balance = %s, updated_at = CURRENT_TIMESTAMP
                        WHERE bucket_id = %s
                        RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                                  target_date, status, created_at, updated_at
                        """,
                        (current_balance, bucket_id),
                    ).fetchone()
                connection.execute(
                    """
                    INSERT INTO bucket_transactions
                    (transaction_id, bucket_id, customer_id, type, amount, status, external_reference, idempotency_key)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        uuid4(),
                        bucket_id,
                        customer_id,
                        transaction_type,
                        amount,
                        status,
                        external_reference,
                        idempotency_key,
                    ),
                )
        return _bucket_from_row(row)


def _bucket_from_row(row: dict) -> BucketRecord:
    return BucketRecord(**row)


def _transaction_from_row(row: dict) -> TransactionRecord:
    return TransactionRecord(**row)
