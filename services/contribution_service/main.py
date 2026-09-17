from fastapi import Depends, FastAPI

from shared.app import create_app
from shared.auth import require_customer_id
from shared.errors import not_implemented
from shared.idempotency import require_idempotency_key


def register_routes(app: FastAPI) -> None:
    @app.post("/v1/buckets/{bucket_id}/contributions", status_code=202)
    async def create_contribution(
        bucket_id: str,
        customer_id: str = Depends(require_customer_id),
        idempotency_key: str = Depends(require_idempotency_key),
    ):
        raise not_implemented("Contribution processing")


app = create_app("contribution-service", register_routes)
