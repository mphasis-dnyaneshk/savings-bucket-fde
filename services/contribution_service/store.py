from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(frozen=True)
class ContributionRecord:
    contribution_id: UUID
    bucket_id: UUID
    customer_id: str
    amount: Decimal
    status: str
    idempotency_key: str
    external_reference: str
    created_at: datetime


class MockContributionStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ContributionRecord] = {}
        self._by_id: dict[UUID, ContributionRecord] = {}

    def create_or_get(
        self,
        customer_id: str,
        bucket_id: UUID,
        amount: Decimal,
        idempotency_key: str,
    ) -> ContributionRecord:
        key = (customer_id, idempotency_key)
        existing = self._records.get(key)
        if existing:
            if existing.bucket_id != bucket_id or existing.amount != amount:
                raise ValueError(
                    "Idempotency key was already used for another request."
                )
            return existing

        now = datetime.now(timezone.utc)
        record = ContributionRecord(
            contribution_id=uuid4(),
            bucket_id=bucket_id,
            customer_id=customer_id,
            amount=amount,
            status="SUCCESS",
            idempotency_key=idempotency_key,
            external_reference=f"mock-contribution-{uuid4().hex[:12]}",
            created_at=now,
        )
        self._records[key] = record
        self._by_id[record.contribution_id] = record
        return record

    def get_by_key(
        self, customer_id: str, idempotency_key: str
    ) -> ContributionRecord | None:
        return self._records.get((customer_id, idempotency_key))

    def get(self, customer_id: str, contribution_id: UUID) -> ContributionRecord | None:
        record = self._by_id.get(contribution_id)
        return record if record and record.customer_id == customer_id else None


mock_store = MockContributionStore()
