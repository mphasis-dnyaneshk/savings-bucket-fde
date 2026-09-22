from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from services.contribution_service.main import app as contribution_app
from services.notification_service.main import app as notification_app
from services.recurring_contribution_service.main import app as recurring_app
from services.withdrawal_service.main import app as withdrawal_app


def test_contribution_is_idempotent_and_customer_scoped() -> None:
    client = TestClient(contribution_app)
    bucket_id = uuid4()
    headers = {"X-Customer-ID": "customer-1", "Idempotency-Key": "contribution-1"}
    payload = {"amount": "25.00"}

    first = client.post(
        f"/v1/buckets/{bucket_id}/contributions", headers=headers, json=payload
    )
    replay = client.post(
        f"/v1/buckets/{bucket_id}/contributions", headers=headers, json=payload
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["contribution_id"] == first.json()["contribution_id"]

    conflicting = client.post(
        f"/v1/buckets/{bucket_id}/contributions",
        headers=headers,
        json={"amount": "30.00"},
    )
    assert conflicting.status_code == 409

    other_customer = client.get(
        f"/v1/contributions/{first.json()['contribution_id']}",
        headers={"X-Customer-ID": "customer-2"},
    )
    assert other_customer.status_code == 404


def test_withdrawal_is_idempotent_and_readable() -> None:
    client = TestClient(withdrawal_app)
    bucket_id = uuid4()
    headers = {"X-Customer-ID": "customer-1", "Idempotency-Key": "withdrawal-1"}

    response = client.post(
        f"/v1/buckets/{bucket_id}/withdrawals",
        headers=headers,
        json={"amount": "10.00"},
    )

    assert response.status_code == 201
    withdrawal_id = response.json()["withdrawal_id"]
    assert UUID(withdrawal_id)
    assert response.json()["status"] == "SUCCESS"

    lookup = client.get(
        f"/v1/withdrawals/{withdrawal_id}",
        headers={"X-Customer-ID": "customer-1"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["amount"] == "10.00"


def test_recurring_schedule_create_list_update_and_lookup() -> None:
    client = TestClient(recurring_app)
    bucket_id = uuid4()
    headers = {"X-Customer-ID": "customer-1"}

    created = client.post(
        f"/v1/buckets/{bucket_id}/recurring-contributions",
        headers=headers,
        json={"amount": "100.00", "frequency": "MONTHLY", "start_date": "2026-10-01"},
    )

    assert created.status_code == 201
    schedule_id = created.json()["schedule_id"]
    assert created.json()["status"] == "ACTIVE"

    listed = client.get(
        f"/v1/buckets/{bucket_id}/recurring-contributions", headers=headers
    )
    assert listed.status_code == 200
    assert listed.json()[0]["schedule_id"] == schedule_id

    updated = client.patch(
        f"/v1/buckets/{bucket_id}/recurring-contributions/{schedule_id}",
        headers=headers,
        json={"status": "PAUSED", "amount": "125.00"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "PAUSED"
    assert updated.json()["amount"] == "125.00"

    lookup = client.get(f"/v1/recurring-contributions/{schedule_id}", headers=headers)
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "PAUSED"


def test_notification_delivery_and_customer_lookup() -> None:
    client = TestClient(notification_app)
    created = client.post(
        "/internal/notifications",
        json={
            "customer_id": "customer-1",
            "event_type": "ContributionCompleted",
            "message": "Your contribution was completed.",
        },
    )

    assert created.status_code == 201
    notification_id = created.json()["notification_id"]

    lookup = client.get(
        f"/v1/notifications/{notification_id}",
        headers={"X-Customer-ID": "customer-1"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "DELIVERED"

    unauthorized = client.get(
        f"/v1/notifications/{notification_id}",
        headers={"X-Customer-ID": "customer-2"},
    )
    assert unauthorized.status_code == 404
