from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException

from shared.app import create_app
from shared.auth import require_customer_id
from services.notification_service.schemas import (
    NotificationRequest,
    NotificationResponse,
)
from services.notification_service.store import NotificationRecord, mock_store


def to_response(record: NotificationRecord) -> NotificationResponse:
    return NotificationResponse(**record.__dict__)


def register_routes(app: FastAPI) -> None:
    @app.get("/internal/status")
    async def status() -> dict[str, str]:
        return {"status": "ready", "mode": "local-noop"}

    @app.post("/internal/notifications", status_code=201)
    async def create_notification(request: NotificationRequest) -> NotificationResponse:
        return to_response(
            mock_store.create(request.customer_id, request.event_type, request.message)
        )

    @app.get("/v1/notifications/{notification_id}")
    async def get_notification(
        notification_id: UUID,
        customer_id: str = Depends(require_customer_id),
    ) -> NotificationResponse:
        record = mock_store.get(customer_id, notification_id)
        if record is None:
            raise HTTPException(status_code=404, detail="Notification not found.")
        return to_response(record)


app = create_app("notification-service", register_routes)
