from dataclasses import dataclass, replace
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ScheduleRecord:
    schedule_id: UUID
    bucket_id: UUID
    customer_id: str
    amount: Decimal
    frequency: str
    start_date: date
    next_execution_date: date
    status: str
    created_at: datetime
    updated_at: datetime


class MockScheduleStore:
    def __init__(self) -> None:
        self._records: dict[UUID, ScheduleRecord] = {}

    def create(
        self,
        customer_id: str,
        bucket_id: UUID,
        amount: Decimal,
        frequency: str,
        start_date: date | None,
    ) -> ScheduleRecord:
        today = start_date or date.today()
        now = datetime.now(timezone.utc)
        record = ScheduleRecord(
            schedule_id=uuid4(),
            bucket_id=bucket_id,
            customer_id=customer_id,
            amount=amount,
            frequency=frequency,
            start_date=today,
            next_execution_date=today,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        self._records[record.schedule_id] = record
        return record

    def list_for_bucket(
        self, customer_id: str, bucket_id: UUID
    ) -> list[ScheduleRecord]:
        return sorted(
            (
                record
                for record in self._records.values()
                if record.customer_id == customer_id and record.bucket_id == bucket_id
            ),
            key=lambda record: record.created_at,
            reverse=True,
        )

    def get(self, customer_id: str, schedule_id: UUID) -> ScheduleRecord | None:
        record = self._records.get(schedule_id)
        return record if record and record.customer_id == customer_id else None

    def update(
        self,
        record: ScheduleRecord,
        amount: Decimal | None,
        frequency: str | None,
        status: str | None,
    ) -> ScheduleRecord:
        updated = replace(
            record,
            amount=amount if amount is not None else record.amount,
            frequency=frequency if frequency is not None else record.frequency,
            status=status if status is not None else record.status,
            updated_at=datetime.now(timezone.utc),
        )
        self._records[record.schedule_id] = updated
        return updated


mock_store = MockScheduleStore()
