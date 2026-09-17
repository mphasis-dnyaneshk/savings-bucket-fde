from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


@dataclass(frozen=True)
class DomainEvent:
    event_id: str
    event_type: str
    aggregate_id: str
    payload: dict[str, Any]
    occurred_at: datetime

    @classmethod
    def create(
        cls, event_type: str, aggregate_id: str, payload: dict[str, Any]
    ) -> "DomainEvent":
        return cls(
            uuid4().hex, event_type, aggregate_id, payload, datetime.now(timezone.utc)
        )
