from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NotificationRequest(BaseModel):
    customer_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=500)


class NotificationResponse(BaseModel):
    notification_id: UUID
    customer_id: str
    event_type: str
    message: str
    status: str
    created_at: datetime
