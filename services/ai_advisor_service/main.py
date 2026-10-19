from datetime import date
from decimal import Decimal
from math import ceil
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException
from psycopg import Error as PostgresError

from services.ai_advisor_service.bedrock import (
    BedrockNotConfigured,
    BedrockUnavailable,
    generate_advice,
)
from services.ai_advisor_service.repository import fetch_customer_snapshot
from services.ai_advisor_service.schemas import (
    AdvisorResponse,
    BucketRecommendationRequest,
    BucketRecommendationsResponse,
    GoalAdjustmentRequest,
    GoalAdjustmentResponse,
    SavingsRecommendationRequest,
    SavingsRecommendationsResponse,
)
from shared.app import create_app
from shared.auth import require_customer_id
from shared.config import Settings


def register_routes(app: FastAPI) -> None:
    def get_snapshot(customer_id: str) -> dict:
        settings: Settings = app.state.settings
        if not settings.database_url:
            raise HTTPException(
                status_code=503,
                detail="AI advice requires DATABASE_URL to use local PostgreSQL data.",
            )
        try:
            return fetch_customer_snapshot(settings.database_url, customer_id)
        except PostgresError as error:
            raise HTTPException(
                status_code=503, detail="Could not read savings data from PostgreSQL."
            ) from error

    def advise(
        feature: str, snapshot: dict, user_input: dict | None = None
    ) -> AdvisorResponse:
        settings: Settings = app.state.settings
        try:
            return generate_advice(
                feature,
                snapshot,
                settings.aws_region,
                settings.bedrock_model_id,
                user_input,
            )
        except BedrockNotConfigured as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except BedrockUnavailable as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

    @app.post("/v1/ai/goal-adjustments", response_model=GoalAdjustmentResponse)
    def goal_adjustments(
        request: GoalAdjustmentRequest,
        customer_id: str = Depends(require_customer_id),
    ) -> GoalAdjustmentResponse:
        snapshot = get_snapshot(customer_id)
        bucket = next(
            (
                item
                for item in snapshot["buckets"]
                if item["bucket_id"] == str(request.bucket_id)
            ),
            None,
        )
        if bucket is None or bucket["status"] == "ARCHIVED":
            raise HTTPException(status_code=404, detail="Bucket not found.")

        projected_months = None
        if request.monthly_contribution is not None:
            remaining = Decimal(bucket["remaining_amount"])
            projected_months = ceil(remaining / request.monthly_contribution)

        advice = advise(
            "intelligent_goal_adjustment",
            {"bucket": bucket, "monthly_activity": snapshot["monthly_activity"]},
            {
                "monthly_contribution": (
                    str(request.monthly_contribution)
                    if request.monthly_contribution
                    else None
                ),
                "projected_months_at_contribution": projected_months,
            },
        )
        return GoalAdjustmentResponse(
            bucket_id=request.bucket_id,
            remaining_amount=bucket["remaining_amount"],
            projected_months_at_contribution=projected_months,
            target_date=bucket["target_date"],
            advice=advice,
        )

    @app.post(
        "/v1/ai/bucket-recommendations",
        response_model=BucketRecommendationsResponse,
    )
    def bucket_recommendations(
        request: BucketRecommendationRequest,
        customer_id: str = Depends(require_customer_id),
    ) -> BucketRecommendationsResponse:
        snapshot = get_snapshot(customer_id)
        return BucketRecommendationsResponse(
            advice=advise(
                "smart_bucket_recommendation",
                snapshot,
                {"priorities": request.priorities},
            )
        )

    @app.post(
        "/v1/ai/savings-recommendations",
        response_model=SavingsRecommendationsResponse,
    )
    def savings_recommendations(
        request: SavingsRecommendationRequest,
        customer_id: str = Depends(require_customer_id),
    ) -> SavingsRecommendationsResponse:
        snapshot = get_snapshot(customer_id)
        return SavingsRecommendationsResponse(
            advice=advise(
                "personal_savings_recommendation",
                snapshot,
                {
                    "monthly_savings_budget": (
                        str(request.monthly_savings_budget)
                        if request.monthly_savings_budget
                        else None
                    )
                },
            )
        )


app = create_app("ai-advisor-service", register_routes)
