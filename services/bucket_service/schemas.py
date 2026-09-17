from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


class CreateBucketRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    target_amount: Decimal = Field(gt=0)
    target_date: date | None = None

    @field_validator("name")
    @classmethod
    def name_must_not_be_blank(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Bucket name must not be blank.")
        return name


class BucketResponse(BaseModel):
    bucket_id: UUID
    customer_id: str
    name: str
    target_amount: Decimal
    current_balance: Decimal
    remaining_amount: Decimal
    progress_percentage: Decimal
    target_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime


class TransactionResponse(BaseModel):
    transaction_id: UUID
    bucket_id: UUID
    type: str
    amount: Decimal
    status: str
    external_reference: str | None
    created_at: datetime
