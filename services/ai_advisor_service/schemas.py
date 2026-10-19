from datetime import date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class GoalAdjustmentRequest(BaseModel):
    bucket_id: UUID
    monthly_contribution: Decimal | None = Field(default=None, gt=0)


class BucketRecommendationRequest(BaseModel):
    priorities: list[str] = Field(default_factory=list, max_length=10)


class SavingsRecommendationRequest(BaseModel):
    monthly_savings_budget: Decimal | None = Field(default=None, gt=0)


class Recommendation(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    detail: str = Field(min_length=1, max_length=600)


class AdvisorResponse(BaseModel):
    summary: str = Field(min_length=1, max_length=600)
    recommendations: list[Recommendation] = Field(min_length=1, max_length=5)
    disclaimer: str = "Suggestions are informational and do not change your buckets."


class GoalAdjustmentResponse(BaseModel):
    bucket_id: UUID
    remaining_amount: Decimal
    projected_months_at_contribution: int | None
    target_date: date | None
    advice: AdvisorResponse


class BucketRecommendationsResponse(BaseModel):
    advice: AdvisorResponse


class SavingsRecommendationsResponse(BaseModel):
    advice: AdvisorResponse
