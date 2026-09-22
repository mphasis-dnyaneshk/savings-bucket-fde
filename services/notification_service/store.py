from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID, uuid4


@dataclass(frozen=True)
class NotificationRecord:
    notification_id: UUID
    customer_id: str
    event_type: str
    message: str
    status: str
    created_at: datetime


class MockNotificationStore:
    def __init__(self) -> None:
        self._records: dict[UUID, NotificationRecord] = {}

    def create(
        self, customer_id: str, event_type: str, message: str
    ) -> NotificationRecord:
        record = NotificationRecord(
            notification_id=uuid4(),
            customer_id=customer_id,
            event_type=event_type,
            message=message,
            status="DELIVERED",
            created_at=datetime.now(timezone.utc),
        )
        self._records[record.notification_id] = record
        return record

    def get(self, customer_id: str, notification_id: UUID) -> NotificationRecord | None:
        record = self._records.get(notification_id)
        return record if record and record.customer_id == customer_id else None

    def dismiss(self, customer_id: str, notification_id: UUID) -> NotificationRecord | None:
        record = self.get(customer_id, notification_id)
        if record is not None:
            del self._records[notification_id]
        return record

    def list_for_customer(self, customer_id: str) -> list[NotificationRecord]:
        return sorted(
            (
                record
                for record in self._records.values()
                if record.customer_id == customer_id
            ),
            key=lambda record: record.created_at,
            reverse=True,
        )


mock_store = MockNotificationStore()
