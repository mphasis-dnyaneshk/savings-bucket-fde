from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from shared.app import create_app
from shared.auth import require_customer_id
from services.recurring_contribution_service.schemas import (
    CreateScheduleRequest,
    ScheduleResponse,
    UpdateScheduleRequest,
)
from services.recurring_contribution_service.store import ScheduleRecord, mock_store


def to_response(record: ScheduleRecord) -> ScheduleResponse:
    return ScheduleResponse(**record.__dict__)


def register_routes(app: FastAPI) -> None:
    @app.post("/v1/buckets/{bucket_id}/recurring-contributions", status_code=201)
    async def create_schedule(
        bucket_id: UUID,
        request: CreateScheduleRequest,
        customer_id: str = Depends(require_customer_id),
    ) -> ScheduleResponse:
        return to_response(
            mock_store.create(
                customer_id,
                bucket_id,
                request.amount,
                request.frequency,
                request.start_date,
            )
        )

    @app.get("/v1/buckets/{bucket_id}/recurring-contributions")
    async def list_schedules(
        bucket_id: UUID,
        customer_id: str = Depends(require_customer_id),
    ) -> list[ScheduleResponse]:
        return [
            to_response(record)
            for record in mock_store.list_for_bucket(customer_id, bucket_id)
        ]

    @app.patch("/v1/buckets/{bucket_id}/recurring-contributions/{schedule_id}")
    async def update_schedule(
        bucket_id: UUID,
        schedule_id: UUID,
        request: UpdateScheduleRequest,
        customer_id: str = Depends(require_customer_id),
    ) -> ScheduleResponse:
        record = mock_store.get(customer_id, schedule_id)
        if record is None or record.bucket_id != bucket_id:
            raise HTTPException(
                status_code=404, detail="Recurring contribution not found."
            )
        return to_response(
            mock_store.update(record, request.amount, request.frequency, request.status)
        )

    @app.get("/v1/recurring-contributions/{schedule_id}")
    async def get_schedule(
        schedule_id: UUID,
        customer_id: str = Depends(require_customer_id),
    ) -> ScheduleResponse:
        record = mock_store.get(customer_id, schedule_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail="Recurring contribution not found."
            )
        return to_response(record)


app = create_app("recurring-contribution-service", register_routes)
