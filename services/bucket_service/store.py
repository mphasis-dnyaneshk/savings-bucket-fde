from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
from threading import Lock
from typing import Protocol
from uuid import UUID, uuid4

import psycopg
from psycopg.rows import dict_row

MAX_BUCKETS_PER_CUSTOMER = 10
BUCKET_LIMIT_MESSAGE = "You can create a maximum of 10 savings buckets per account."


def over_target_contribution_message(remaining_amount: Decimal) -> str:
    return (
        "This contribution exceeds the remaining target of "
        f"{remaining_amount:.2f}. Confirm the full amount to continue."
    )


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
    reached_at: datetime | None
    archived_at: datetime | None


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: UUID
    bucket_id: UUID
    customer_id: str
    type: str
    amount: Decimal
    status: str
    external_reference: str | None
    idempotency_key: str
    created_at: datetime


@dataclass(frozen=True)
class TransactionApplicationResult:
    bucket: BucketRecord
    goal_reached_now: bool


class BucketStore(Protocol):
    def create_bucket(
        self,
        customer_id: str,
        name: str,
        target_amount: Decimal,
        target_date: date | None,
    ) -> BucketRecord: ...

    def list_buckets(self, customer_id: str) -> list[BucketRecord]: ...

    def list_archived_buckets(self, customer_id: str) -> list[BucketRecord]: ...

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None: ...

    def update_target_amount(
        self, customer_id: str, bucket_id: UUID, target_amount: Decimal
    ) -> BucketRecord | None: ...

    def archive_bucket(
        self, customer_id: str, bucket_id: UUID
    ) -> BucketRecord | None: ...

    def restore_bucket(
        self, customer_id: str, bucket_id: UUID
    ) -> BucketRecord | None: ...

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
        allow_over_target: bool,
    ) -> TransactionApplicationResult: ...


class InMemoryBucketStore:
    def __init__(self) -> None:
        self._buckets: dict[UUID, BucketRecord] = {}
        self._transactions: list[TransactionRecord] = []
        self._creation_lock = Lock()

    def create_bucket(
        self,
        customer_id: str,
        name: str,
        target_amount: Decimal,
        target_date: date | None,
    ) -> BucketRecord:
        with self._creation_lock:
            if (
                sum(
                    bucket.customer_id == customer_id and bucket.status != "ARCHIVED"
                    for bucket in self._buckets.values()
                )
                >= MAX_BUCKETS_PER_CUSTOMER
            ):
                raise ValueError(BUCKET_LIMIT_MESSAGE)
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
                reached_at=None,
                archived_at=None,
            )
            self._buckets[record.bucket_id] = record
            return record

    def list_buckets(self, customer_id: str) -> list[BucketRecord]:
        return sorted(
            (
                bucket
                for bucket in self._buckets.values()
                if bucket.customer_id == customer_id and bucket.status != "ARCHIVED"
            ),
            key=lambda bucket: bucket.created_at,
            reverse=True,
        )

    def list_archived_buckets(self, customer_id: str) -> list[BucketRecord]:
        return sorted(
            (
                bucket
                for bucket in self._buckets.values()
                if bucket.customer_id == customer_id and bucket.status == "ARCHIVED"
            ),
            key=lambda bucket: bucket.archived_at or bucket.updated_at,
            reverse=True,
        )

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        bucket = self._buckets.get(bucket_id)
        return bucket if bucket and bucket.customer_id == customer_id else None

    def update_target_amount(
        self, customer_id: str, bucket_id: UUID, target_amount: Decimal
    ) -> BucketRecord | None:
        with self._creation_lock:
            bucket = self.get_bucket(customer_id, bucket_id)
            if bucket is None:
                return None
            if bucket.status == "ARCHIVED":
                raise ValueError(
                    "Restore this archived goal before changing its target."
                )
            reached = bucket.current_balance >= target_amount
            updated = replace(
                bucket,
                target_amount=target_amount,
                status="REACHED" if reached else "ACTIVE",
                reached_at=(
                    bucket.reached_at
                    or (datetime.now(timezone.utc) if reached else None)
                ),
                updated_at=datetime.now(timezone.utc),
            )
            self._buckets[bucket_id] = updated
            return updated

    def archive_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with self._creation_lock:
            bucket = self.get_bucket(customer_id, bucket_id)
            if bucket is None:
                return None
            if bucket.status == "ARCHIVED":
                return bucket
            if bucket.reached_at is None:
                raise ValueError("Only a goal that has been reached can be archived.")
            if bucket.current_balance != 0:
                raise ValueError("Withdraw the full goal balance before archiving it.")
            now = datetime.now(timezone.utc)
            archived = replace(
                bucket,
                status="ARCHIVED",
                archived_at=now,
                updated_at=now,
            )
            self._buckets[bucket_id] = archived
            return archived

    def restore_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with self._creation_lock:
            bucket = self.get_bucket(customer_id, bucket_id)
            if bucket is None or bucket.status != "ARCHIVED":
                return None
            active_count = sum(
                item.customer_id == customer_id and item.status != "ARCHIVED"
                for item in self._buckets.values()
            )
            if active_count >= MAX_BUCKETS_PER_CUSTOMER:
                raise ValueError(BUCKET_LIMIT_MESSAGE)
            restored = replace(
                bucket,
                status=(
                    "REACHED"
                    if bucket.current_balance >= bucket.target_amount
                    else "ACTIVE"
                ),
                archived_at=None,
                updated_at=datetime.now(timezone.utc),
            )
            self._buckets[bucket_id] = restored
            return restored

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
        allow_over_target: bool,
    ) -> TransactionApplicationResult:
        with self._creation_lock:
            bucket = self.get_bucket(customer_id, bucket_id)
            if bucket is None:
                raise LookupError("Bucket not found.")
            if any(
                transaction.customer_id == customer_id
                and transaction.idempotency_key == idempotency_key
                for transaction in self._transactions
            ):
                return TransactionApplicationResult(bucket, False)
            if bucket.status == "ARCHIVED":
                raise ValueError(
                    "Restore this archived goal before adding transactions."
                )
            previous_balance = bucket.current_balance
            balance = previous_balance
            if status == "SUCCESS":
                if (
                    transaction_type == "CONTRIBUTION"
                    and amount
                    > max(bucket.target_amount - previous_balance, Decimal("0"))
                    and not allow_over_target
                ):
                    remaining_amount = max(
                        bucket.target_amount - previous_balance, Decimal("0")
                    )
                    raise ValueError(over_target_contribution_message(remaining_amount))
                balance = (
                    previous_balance + amount
                    if transaction_type == "CONTRIBUTION"
                    else previous_balance - amount
                )
                if balance < 0:
                    raise ValueError("Withdrawal exceeds available bucket balance.")
            now = datetime.now(timezone.utc)
            reached = balance >= bucket.target_amount
            updated = replace(
                bucket,
                current_balance=balance,
                status="REACHED" if reached else "ACTIVE",
                reached_at=(
                    bucket.reached_at
                    or (
                        now
                        if transaction_type == "CONTRIBUTION"
                        and previous_balance < bucket.target_amount
                        and reached
                        else None
                    )
                ),
                updated_at=now,
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
                    idempotency_key=idempotency_key,
                    created_at=now,
                )
            )
            return TransactionApplicationResult(
                updated,
                transaction_type == "CONTRIBUTION"
                and previous_balance < bucket.target_amount
                and reached,
            )


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
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (customer_id,),
                )
                bucket_count = connection.execute(
                    "SELECT COUNT(*) FROM buckets WHERE customer_id = %s AND status <> 'ARCHIVED'",
                    (customer_id,),
                ).fetchone()["count"]
                if bucket_count >= MAX_BUCKETS_PER_CUSTOMER:
                    raise ValueError(BUCKET_LIMIT_MESSAGE)
                row = connection.execute(
                    """
                    INSERT INTO buckets (bucket_id, customer_id, name, target_amount, target_date)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                              target_date, status, created_at, updated_at, reached_at, archived_at
                    """,
                    (bucket_id, customer_id, name, target_amount, target_date),
                ).fetchone()
        return _bucket_from_row(row)

    def list_buckets(self, customer_id: str) -> list[BucketRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT bucket_id, customer_id, name, target_amount, current_balance,
                      target_date, status, created_at, updated_at, reached_at, archived_at
                FROM buckets
                  WHERE customer_id = %s AND status <> 'ARCHIVED'
                ORDER BY created_at DESC
                """,
                (customer_id,),
            ).fetchall()
        return [_bucket_from_row(row) for row in rows]

    def list_archived_buckets(self, customer_id: str) -> list[BucketRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                SELECT bucket_id, customer_id, name, target_amount, current_balance,
                       target_date, status, created_at, updated_at, reached_at, archived_at
                FROM buckets
                WHERE customer_id = %s AND status = 'ARCHIVED'
                ORDER BY archived_at DESC
                """,
                (customer_id,),
            ).fetchall()
        return [_bucket_from_row(row) for row in rows]

    def get_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                SELECT bucket_id, customer_id, name, target_amount, current_balance,
                      target_date, status, created_at, updated_at, reached_at, archived_at
                FROM buckets
                WHERE bucket_id = %s AND customer_id = %s
                """,
                (bucket_id, customer_id),
            ).fetchone()
        return _bucket_from_row(row) if row else None

    def update_target_amount(
        self, customer_id: str, bucket_id: UUID, target_amount: Decimal
    ) -> BucketRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            row = connection.execute(
                """
                UPDATE buckets
                SET target_amount = %s,
                    status = CASE WHEN current_balance >= %s THEN 'REACHED' ELSE 'ACTIVE' END,
                    reached_at = CASE
                        WHEN current_balance >= %s THEN COALESCE(reached_at, CURRENT_TIMESTAMP)
                        ELSE reached_at
                    END,
                    updated_at = CURRENT_TIMESTAMP
                WHERE bucket_id = %s AND customer_id = %s AND status <> 'ARCHIVED'
                RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                          target_date, status, created_at, updated_at, reached_at, archived_at
                """,
                (target_amount, target_amount, target_amount, bucket_id, customer_id),
            ).fetchone()
        return _bucket_from_row(row) if row else None

    def archive_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT bucket_id, customer_id, name, target_amount, current_balance,
                           target_date, status, created_at, updated_at, reached_at, archived_at
                    FROM buckets
                    WHERE bucket_id = %s AND customer_id = %s
                    FOR UPDATE
                    """,
                    (bucket_id, customer_id),
                ).fetchone()
                if row is None:
                    return None
                if row["status"] == "ARCHIVED":
                    return _bucket_from_row(row)
                if row["reached_at"] is None:
                    raise ValueError(
                        "Only a goal that has been reached can be archived."
                    )
                if row["current_balance"] != 0:
                    raise ValueError(
                        "Withdraw the full goal balance before archiving it."
                    )
                row = connection.execute(
                    """
                    UPDATE buckets
                    SET status = 'ARCHIVED', archived_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE bucket_id = %s
                    RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                              target_date, status, created_at, updated_at, reached_at, archived_at
                    """,
                    (bucket_id,),
                ).fetchone()
        return _bucket_from_row(row)

    def restore_bucket(self, customer_id: str, bucket_id: UUID) -> BucketRecord | None:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                    (customer_id,),
                )
                row = connection.execute(
                    """
                    SELECT bucket_id, customer_id, name, target_amount, current_balance,
                           target_date, status, created_at, updated_at, reached_at, archived_at
                    FROM buckets
                    WHERE bucket_id = %s AND customer_id = %s AND status = 'ARCHIVED'
                    FOR UPDATE
                    """,
                    (bucket_id, customer_id),
                ).fetchone()
                if row is None:
                    return None
                active_count = connection.execute(
                    "SELECT COUNT(*) FROM buckets WHERE customer_id = %s AND status <> 'ARCHIVED'",
                    (customer_id,),
                ).fetchone()["count"]
                if active_count >= MAX_BUCKETS_PER_CUSTOMER:
                    raise ValueError(BUCKET_LIMIT_MESSAGE)
                row = connection.execute(
                    """
                    UPDATE buckets
                    SET status = CASE WHEN current_balance >= target_amount THEN 'REACHED' ELSE 'ACTIVE' END,
                        archived_at = NULL,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE bucket_id = %s
                    RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                              target_date, status, created_at, updated_at, reached_at, archived_at
                    """,
                    (bucket_id,),
                ).fetchone()
        return _bucket_from_row(row)

    def list_transactions(
        self, customer_id: str, bucket_id: UUID
    ) -> list[TransactionRecord]:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            rows = connection.execute(
                """
                  SELECT transaction_id, bucket_id, customer_id, type, amount, status,
                      external_reference, idempotency_key, created_at
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
        allow_over_target: bool,
    ) -> TransactionApplicationResult:
        with psycopg.connect(self.database_url, row_factory=dict_row) as connection:
            with connection.transaction():
                row = connection.execute(
                    """
                    SELECT bucket_id, customer_id, name, target_amount, current_balance,
                              target_date, status, created_at, updated_at, reached_at, archived_at
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
                    return TransactionApplicationResult(_bucket_from_row(row), False)
                if row["status"] == "ARCHIVED":
                    raise ValueError(
                        "Restore this archived goal before adding transactions."
                    )
                previous_balance = row["current_balance"]
                current_balance = row["current_balance"]
                if status == "SUCCESS":
                    if (
                        transaction_type == "CONTRIBUTION"
                        and amount
                        > max(row["target_amount"] - previous_balance, Decimal("0"))
                        and not allow_over_target
                    ):
                        remaining_amount = max(
                            row["target_amount"] - previous_balance, Decimal("0")
                        )
                        raise ValueError(
                            over_target_contribution_message(remaining_amount)
                        )
                    current_balance = (
                        current_balance + amount
                        if transaction_type == "CONTRIBUTION"
                        else current_balance - amount
                    )
                    if current_balance < 0:
                        raise ValueError("Withdrawal exceeds available bucket balance.")
                    next_status = (
                        "REACHED"
                        if current_balance >= row["target_amount"]
                        else "ACTIVE"
                    )
                    row = connection.execute(
                        """
                        UPDATE buckets
                        SET current_balance = %s,
                            status = %s,
                            reached_at = CASE
                                WHEN %s THEN COALESCE(reached_at, CURRENT_TIMESTAMP)
                                ELSE reached_at
                            END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE bucket_id = %s
                        RETURNING bucket_id, customer_id, name, target_amount, current_balance,
                                  target_date, status, created_at, updated_at, reached_at, archived_at
                        """,
                        (
                            current_balance,
                            next_status,
                            transaction_type == "CONTRIBUTION"
                            and previous_balance < row["target_amount"]
                            and current_balance >= row["target_amount"],
                            bucket_id,
                        ),
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
        updated_bucket = _bucket_from_row(row)
        return TransactionApplicationResult(
            updated_bucket,
            status == "SUCCESS"
            and transaction_type == "CONTRIBUTION"
            and previous_balance < row["target_amount"]
            and updated_bucket.current_balance >= updated_bucket.target_amount,
        )


def _bucket_from_row(row: dict) -> BucketRecord:
    return BucketRecord(**row)


def _transaction_from_row(row: dict) -> TransactionRecord:
    return TransactionRecord(**row)
