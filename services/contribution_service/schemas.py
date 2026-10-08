from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ContributionRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    allow_over_target: bool = False


class ContributionResponse(BaseModel):
    contribution_id: UUID
    bucket_id: UUID
    customer_id: str
    amount: Decimal
    status: str
    idempotency_key: str
    external_reference: str
    created_at: datetime
    goal_reached_now: bool = False
    bucket_current_balance: Decimal | None = None
    bucket_target_amount: Decimal | None = None
    bucket_remaining_amount: Decimal | None = None
    bucket_progress_percentage: Decimal | None = None
    bucket_status: str | None = None
