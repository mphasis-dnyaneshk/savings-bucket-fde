from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from services.contribution_service.main import app as contribution_app
from services.notification_service.main import app as notification_app
from services.recurring_contribution_service.main import app as recurring_app
from services.withdrawal_service.main import app as withdrawal_app


def test_contribution_replay_retries_bucket_apply_and_keeps_transition_one_time(
    monkeypatch,
) -> None:
    bucket_responses = iter(
        [
            {
                "goal_reached_now": True,
                "current_balance": "125.00",
                "target_amount": "100.00",
                "remaining_amount": "0.00",
                "progress_percentage": "100.00",
                "status": "REACHED",
            },
            {
                "goal_reached_now": False,
                "current_balance": "125.00",
                "target_amount": "100.00",
                "remaining_amount": "0.00",
                "progress_percentage": "100.00",
                "status": "REACHED",
            },
        ]
    )
    bucket_apply_calls = 0
    allow_over_target_values = []

    class MockResponse:
        status_code = 200

        def __init__(self, body):
            self.body = body

        def json(self):
            return self.body

    class MockAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, *args, **kwargs):
            nonlocal bucket_apply_calls
            bucket_apply_calls += 1
            allow_over_target_values.append(kwargs["json"]["allow_over_target"])
            return MockResponse(next(bucket_responses))

    monkeypatch.setattr(
        "services.contribution_service.main.httpx.AsyncClient", MockAsyncClient
    )
    client = TestClient(contribution_app)
    bucket_id = uuid4()
    headers = {
        "X-Customer-ID": f"customer-{uuid4()}",
        "Idempotency-Key": f"contribution-{uuid4()}",
    }
    payload = {"amount": "125.00", "allow_over_target": True}

    first = client.post(
        f"/v1/buckets/{bucket_id}/contributions", headers=headers, json=payload
    )
    replay = client.post(
        f"/v1/buckets/{bucket_id}/contributions", headers=headers, json=payload
    )

    assert first.status_code == 201
    assert replay.status_code == 201
    assert replay.json()["contribution_id"] == first.json()["contribution_id"]
    assert first.json()["goal_reached_now"] is True
    assert replay.json()["goal_reached_now"] is False
    assert replay.json()["bucket_current_balance"] == "125.00"
    assert bucket_apply_calls == 2
    assert allow_over_target_values == [True, True]

    conflicting = client.post(
        f"/v1/buckets/{bucket_id}/contributions",
        headers=headers,
        json={"amount": "130.00"},
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

    listed = client.get(
        "/v1/notifications",
        headers={"X-Customer-ID": "customer-1"},
    )
    assert listed.status_code == 200
    assert listed.json()[0]["notification_id"] == notification_id

    lookup = client.get(
        f"/v1/notifications/{notification_id}",
        headers={"X-Customer-ID": "customer-1"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "DELIVERED"

    dismissed = client.delete(
        f"/v1/notifications/{notification_id}",
        headers={"X-Customer-ID": "customer-1"},
    )
    assert dismissed.status_code == 200
    assert (
        client.get("/v1/notifications", headers={"X-Customer-ID": "customer-1"}).json()
        == []
    )

    unauthorized = client.get(
        f"/v1/notifications/{notification_id}",
        headers={"X-Customer-ID": "customer-2"},
    )
    assert unauthorized.status_code == 404


def test_clear_all_notifications_is_customer_scoped() -> None:
    client = TestClient(notification_app)
    customer_id = f"clear-{uuid4()}"
    other_customer_id = f"other-{uuid4()}"

    for event_type in ("ContributionCompleted", "GoalReached"):
        response = client.post(
            "/internal/notifications",
            json={
                "customer_id": customer_id,
                "event_type": event_type,
                "message": "Test notification.",
            },
        )
        assert response.status_code == 201

    other_notification = client.post(
        "/internal/notifications",
        json={
            "customer_id": other_customer_id,
            "event_type": "GoalReached",
            "message": "Another customer's notification.",
        },
    )
    assert other_notification.status_code == 201

    cleared = client.delete(
        "/v1/notifications",
        headers={"X-Customer-ID": customer_id},
    )
    assert cleared.status_code == 200
    assert cleared.json()["deleted_count"] == 2
    assert (
        client.get("/v1/notifications", headers={"X-Customer-ID": customer_id}).json()
        == []
    )
    remaining = client.get(
        "/v1/notifications", headers={"X-Customer-ID": other_customer_id}
    )
    assert len(remaining.json()) == 1
