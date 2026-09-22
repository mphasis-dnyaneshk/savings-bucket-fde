from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status

from shared.app import create_app
from shared.auth import require_customer_id
from shared.idempotency import require_idempotency_key
from services.contribution_service.schemas import (
    ContributionRequest,
    ContributionResponse,
)
from services.contribution_service.store import ContributionRecord, mock_store


def to_response(record: ContributionRecord) -> ContributionResponse:
    return ContributionResponse(**record.__dict__)


def register_routes(app: FastAPI) -> None:
    @app.post("/v1/buckets/{bucket_id}/contributions", status_code=201)
    async def create_contribution(
        bucket_id: UUID,
        request: ContributionRequest,
        customer_id: str = Depends(require_customer_id),
        idempotency_key: str = Depends(require_idempotency_key),
    ) -> ContributionResponse:
        try:
            record = mock_store.create_or_get(
                customer_id, bucket_id, request.amount, idempotency_key
            )
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
        return to_response(record)

    @app.get("/v1/contributions/{contribution_id}")
    async def get_contribution(
        contribution_id: UUID,
        customer_id: str = Depends(require_customer_id),
    ) -> ContributionResponse:
        record = mock_store.get(customer_id, contribution_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Contribution not found.")
        return to_response(record)


app = create_app("contribution-service", register_routes)
