from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class ContributionRequest(BaseModel):
    amount: Decimal = Field(gt=0)


class ContributionResponse(BaseModel):
    contribution_id: UUID
    bucket_id: UUID
    customer_id: str
    amount: Decimal
    status: str
    idempotency_key: str
    external_reference: str
    created_at: datetime
