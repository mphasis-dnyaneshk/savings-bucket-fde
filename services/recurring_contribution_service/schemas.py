from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CreateScheduleRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    frequency: str = Field(min_length=1, max_length=32)
    start_date: date | None = None


class UpdateScheduleRequest(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    frequency: str | None = Field(default=None, min_length=1, max_length=32)
    status: str | None = Field(default=None, pattern="^(ACTIVE|PAUSED|CANCELLED)$")


class ScheduleResponse(BaseModel):
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
