from fastapi import Depends, FastAPI

from shared.app import create_app
from shared.auth import require_customer_id
from shared.errors import not_implemented


def register_routes(app: FastAPI) -> None:
    @app.post("/v1/buckets/{bucket_id}/recurring-contributions", status_code=201)
    async def create_schedule(
        bucket_id: str, customer_id: str = Depends(require_customer_id)
    ):
        raise not_implemented("Recurring contribution scheduling")

    @app.patch("/v1/buckets/{bucket_id}/recurring-contributions/{schedule_id}")
    async def update_schedule(
        bucket_id: str,
        schedule_id: str,
        customer_id: str = Depends(require_customer_id),
    ):
        raise not_implemented("Recurring contribution updates")


app = create_app("recurring-contribution-service", register_routes)
