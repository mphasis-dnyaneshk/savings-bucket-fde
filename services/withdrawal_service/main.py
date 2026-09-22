from uuid import UUID

import httpx
from fastapi import Depends, FastAPI, HTTPException, status

from shared.app import create_app
from shared.auth import require_customer_id
from shared.config import get_settings
from shared.idempotency import require_idempotency_key
from services.withdrawal_service.schemas import WithdrawalRequest, WithdrawalResponse
from services.withdrawal_service.store import WithdrawalRecord, mock_store


def to_response(record: WithdrawalRecord) -> WithdrawalResponse:
    return WithdrawalResponse(**record.__dict__)


def register_routes(app: FastAPI) -> None:
    @app.post("/v1/buckets/{bucket_id}/withdrawals", status_code=201)
    async def create_withdrawal(
        bucket_id: UUID,
        request: WithdrawalRequest,
        customer_id: str = Depends(require_customer_id),
        idempotency_key: str = Depends(require_idempotency_key),
    ) -> WithdrawalResponse:
        existing = mock_store.get_by_key(customer_id, idempotency_key)
        if existing:
            if existing.bucket_id != bucket_id or existing.amount != request.amount:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Idempotency key was already used for another request.",
                )
            return to_response(existing)
        try:
            record = mock_store.create_or_get(
                customer_id, bucket_id, request.amount, idempotency_key
            )
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(
                    f"{get_settings().bucket_service_url}/internal/buckets/{bucket_id}/transactions",
                    headers={"X-Customer-ID": customer_id},
                    json={
                        "type": "WITHDRAWAL",
                        "amount": str(record.amount),
                        "status": record.status,
                        "external_reference": record.external_reference,
                        "idempotency_key": record.idempotency_key,
                    },
                )
            if response.status_code >= 400:
                detail = response.json().get(
                    "detail", "Bucket allocation update failed."
                )
                raise HTTPException(status_code=response.status_code, detail=detail)
        except httpx.RequestError as error:
            raise HTTPException(
                status_code=503, detail="Bucket service is unavailable."
            ) from error
        return to_response(record)

    @app.get("/v1/withdrawals/{withdrawal_id}")
    async def get_withdrawal(
        withdrawal_id: UUID,
        customer_id: str = Depends(require_customer_id),
    ) -> WithdrawalResponse:
        record = mock_store.get(customer_id, withdrawal_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Withdrawal not found.")
        return to_response(record)


app = create_app("withdrawal-service", register_routes)
