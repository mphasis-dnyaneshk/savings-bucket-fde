from fastapi import Depends, FastAPI

from shared.app import create_app
from shared.auth import require_customer_id
from shared.errors import not_implemented


def register_routes(app: FastAPI) -> None:
    @app.get("/v1/buckets")
    async def list_buckets(customer_id: str = Depends(require_customer_id)):
        raise not_implemented("Bucket listing")

    @app.post("/v1/buckets", status_code=201)
    async def create_bucket(customer_id: str = Depends(require_customer_id)):
        raise not_implemented("Bucket creation")

    @app.get("/v1/buckets/{bucket_id}")
    async def get_bucket(
        bucket_id: str, customer_id: str = Depends(require_customer_id)
    ):
        raise not_implemented("Bucket details")

    @app.get("/v1/buckets/{bucket_id}/transactions")
    async def list_transactions(
        bucket_id: str, customer_id: str = Depends(require_customer_id)
    ):
        raise not_implemented("Transaction history")


app = create_app("bucket-service", register_routes)
