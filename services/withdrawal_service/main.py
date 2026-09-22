from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status

from shared.app import create_app
from shared.auth import require_customer_id
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
        try:
            record = mock_store.create_or_get(
                customer_id, bucket_id, request.amount, idempotency_key
            )
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
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
