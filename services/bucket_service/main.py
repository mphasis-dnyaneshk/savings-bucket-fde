from decimal import Decimal
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, status

from shared.app import create_app
from shared.auth import require_customer_id
from shared.config import get_settings
from services.bucket_service.schemas import (
    BucketResponse,
    CreateBucketRequest,
    ApplyTransactionRequest,
    TransactionResponse,
)
from services.bucket_service.store import (
    BucketRecord,
    BucketStore,
    InMemoryBucketStore,
    PostgresBucketStore,
    TransactionRecord,
)


def get_bucket_store(app: FastAPI) -> BucketStore:
    return app.state.bucket_store


def to_bucket_response(bucket: BucketRecord) -> BucketResponse:
    remaining = max(bucket.target_amount - bucket.current_balance, Decimal("0"))
    progress = min(
        (bucket.current_balance / bucket.target_amount) * Decimal("100"), Decimal("100")
    )
    return BucketResponse(
        bucket_id=bucket.bucket_id,
        customer_id=bucket.customer_id,
        name=bucket.name,
        target_amount=bucket.target_amount,
        current_balance=bucket.current_balance,
        remaining_amount=remaining,
        progress_percentage=progress.quantize(Decimal("0.01")),
        target_date=bucket.target_date,
        status=bucket.status,
        created_at=bucket.created_at,
        updated_at=bucket.updated_at,
    )


def to_transaction_response(transaction: TransactionRecord) -> TransactionResponse:
    return TransactionResponse(
        transaction_id=transaction.transaction_id,
        bucket_id=transaction.bucket_id,
        type=transaction.type,
        amount=transaction.amount,
        status=transaction.status,
        external_reference=transaction.external_reference,
        created_at=transaction.created_at,
    )


def register_routes(app: FastAPI) -> None:
    @app.post("/internal/buckets/{bucket_id}/transactions")
    async def apply_transaction(
        bucket_id: UUID,
        request: ApplyTransactionRequest,
        customer_id: str = Depends(require_customer_id),
        store: BucketStore = Depends(lambda: get_bucket_store(app)),
    ) -> BucketResponse:
        try:
            bucket = store.apply_transaction(
                customer_id,
                bucket_id,
                request.type,
                request.amount,
                request.status,
                request.external_reference,
                request.idempotency_key,
            )
        except LookupError as error:
            raise HTTPException(status_code=404, detail=str(error))
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error))
        return to_bucket_response(bucket)

    @app.get("/v1/buckets")
    async def list_buckets(
        customer_id: str = Depends(require_customer_id),
        store: BucketStore = Depends(lambda: get_bucket_store(app)),
    ) -> list[BucketResponse]:
        return [
            to_bucket_response(bucket) for bucket in store.list_buckets(customer_id)
        ]

    @app.post("/v1/buckets", status_code=201)
    async def create_bucket(
        request: CreateBucketRequest,
        customer_id: str = Depends(require_customer_id),
        store: BucketStore = Depends(lambda: get_bucket_store(app)),
    ) -> BucketResponse:
        bucket = store.create_bucket(
            customer_id=customer_id,
            name=request.name,
            target_amount=request.target_amount,
            target_date=request.target_date,
        )
        return to_bucket_response(bucket)

    @app.get("/v1/buckets/{bucket_id}")
    async def get_bucket(
        bucket_id: UUID,
        customer_id: str = Depends(require_customer_id),
        store: BucketStore = Depends(lambda: get_bucket_store(app)),
    ) -> BucketResponse:
        bucket = store.get_bucket(customer_id, bucket_id)
        if bucket is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bucket not found.",
            )
        return to_bucket_response(bucket)

    @app.get("/v1/buckets/{bucket_id}/transactions")
    async def list_transactions(
        bucket_id: UUID,
        customer_id: str = Depends(require_customer_id),
        store: BucketStore = Depends(lambda: get_bucket_store(app)),
    ) -> list[TransactionResponse]:
        if store.get_bucket(customer_id, bucket_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bucket not found.",
            )
        return [
            to_transaction_response(transaction)
            for transaction in store.list_transactions(customer_id, bucket_id)
        ]


app = create_app("bucket-service", register_routes)
settings = get_settings()
app.state.bucket_store = (
    PostgresBucketStore(settings.database_url)
    if settings.database_url
    else InMemoryBucketStore()
)
