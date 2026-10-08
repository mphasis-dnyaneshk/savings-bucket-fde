from fastapi.testclient import TestClient
from uuid import UUID

from services.bucket_service.main import app

client = TestClient(app)


def test_service_root() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json() == {
        "service": "bucket-service",
        "status": "ok",
        "health": "/health/live",
        "docs": "/docs",
    }


def test_liveness() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "bucket-service"


def test_bucket_routes_require_local_identity() -> None:
    response = client.get("/v1/buckets")

    assert response.status_code == 401


def test_bucket_lifecycle_for_customer() -> None:
    headers = {"X-Customer-ID": "customer-1"}
    create_response = client.post(
        "/v1/buckets",
        headers=headers,
        json={
            "name": "Emergency Fund",
            "target_amount": "1000.00",
            "target_date": "2027-12-31",
        },
    )

    assert create_response.status_code == 201
    created = create_response.json()
    bucket_id = created["bucket_id"]
    assert UUID(bucket_id)
    assert created["current_balance"] == "0.00"
    assert created["remaining_amount"] == "1000.00"
    assert created["progress_percentage"] == "0.00"

    archive_unreached = client.post(
        f"/v1/buckets/{created['bucket_id']}/archive",
        headers=headers,
    )
    assert archive_unreached.status_code == 422

    list_response = client.get("/v1/buckets", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()[0]["bucket_id"] == bucket_id

    detail_response = client.get(f"/v1/buckets/{bucket_id}", headers=headers)
    assert detail_response.status_code == 200
    assert detail_response.json()["name"] == "Emergency Fund"

    history_response = client.get(
        f"/v1/buckets/{bucket_id}/transactions", headers=headers
    )
    assert history_response.status_code == 200
    assert history_response.json() == []


def test_bucket_isolation_and_validation() -> None:
    create_response = client.post(
        "/v1/buckets",
        headers={"X-Customer-ID": "customer-owner"},
        json={"name": "Vacation", "target_amount": "500"},
    )
    bucket_id = create_response.json()["bucket_id"]

    unauthorized_response = client.get(
        f"/v1/buckets/{bucket_id}", headers={"X-Customer-ID": "other-customer"}
    )
    assert unauthorized_response.status_code == 404

    invalid_response = client.post(
        "/v1/buckets",
        headers={"X-Customer-ID": "customer-owner"},
        json={"name": " ", "target_amount": "0"},
    )
    assert invalid_response.status_code == 422


def test_customer_can_create_at_most_ten_buckets() -> None:
    customer_id = f"bucket-limit-{UUID(int=1)}"
    headers = {"X-Customer-ID": customer_id}

    for bucket_number in range(10):
        response = client.post(
            "/v1/buckets",
            headers=headers,
            json={"name": f"Goal {bucket_number + 1}", "target_amount": "100"},
        )
        assert response.status_code == 201

    limit_response = client.post(
        "/v1/buckets",
        headers=headers,
        json={"name": "Goal 11", "target_amount": "100"},
    )
    assert limit_response.status_code == 422
    assert limit_response.json()["detail"] == (
        "You can create a maximum of 10 savings buckets per account."
    )

    other_customer_response = client.post(
        "/v1/buckets",
        headers={"X-Customer-ID": "another-account"},
        json={"name": "First goal", "target_amount": "100"},
    )
    assert other_customer_response.status_code == 201


def test_goal_reached_transition_is_one_time_and_target_can_change() -> None:
    customer_id = f"goal-reached-{UUID(int=2)}"
    headers = {"X-Customer-ID": customer_id}
    created = client.post(
        "/v1/buckets",
        headers=headers,
        json={"name": "Travel", "target_amount": "100"},
    )
    bucket_id = created.json()["bucket_id"]
    transaction = {
        "type": "CONTRIBUTION",
        "amount": "125",
        "status": "SUCCESS",
        "external_reference": "goal-reached-contribution",
        "idempotency_key": "goal-reached-contribution-1",
    }

    unconfirmed = client.post(
        f"/internal/buckets/{bucket_id}/transactions",
        headers=headers,
        json=transaction,
    )
    assert unconfirmed.status_code == 422
    assert "Confirm the full amount" in unconfirmed.json()["detail"]

    transaction["allow_over_target"] = True
    reached = client.post(
        f"/internal/buckets/{bucket_id}/transactions",
        headers=headers,
        json=transaction,
    )
    assert reached.status_code == 200
    assert reached.json()["goal_reached_now"] is True
    assert reached.json()["status"] == "REACHED"
    assert reached.json()["current_balance"] == "125.00"
    assert reached.json()["remaining_amount"] == "0.00"
    assert reached.json()["progress_percentage"] == "100.00"

    replay = client.post(
        f"/internal/buckets/{bucket_id}/transactions",
        headers=headers,
        json=transaction,
    )
    assert replay.status_code == 200
    assert replay.json()["goal_reached_now"] is False
    assert replay.json()["current_balance"] == "125.00"

    updated = client.patch(
        f"/v1/buckets/{bucket_id}",
        headers=headers,
        json={"target_amount": "150"},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "ACTIVE"
    assert updated.json()["remaining_amount"] == "25.00"
    assert updated.json()["reached_at"] is not None

    reached_again = client.post(
        f"/internal/buckets/{bucket_id}/transactions",
        headers=headers,
        json={
            "type": "CONTRIBUTION",
            "amount": "25",
            "status": "SUCCESS",
            "external_reference": "goal-reached-contribution-2",
            "idempotency_key": "goal-reached-contribution-2",
        },
    )
    assert reached_again.status_code == 200
    assert reached_again.json()["status"] == "REACHED"

    cannot_archive_with_balance = client.post(
        f"/v1/buckets/{bucket_id}/archive", headers=headers
    )
    assert cannot_archive_with_balance.status_code == 422

    withdrawn = client.post(
        f"/internal/buckets/{bucket_id}/transactions",
        headers=headers,
        json={
            "type": "WITHDRAWAL",
            "amount": "150",
            "status": "SUCCESS",
            "external_reference": "goal-emptying-withdrawal",
            "idempotency_key": "goal-emptying-withdrawal-1",
        },
    )
    assert withdrawn.status_code == 200
    assert withdrawn.json()["current_balance"] == "0.00"
    assert withdrawn.json()["status"] == "ACTIVE"
    assert withdrawn.json()["reached_at"] is not None

    archived = client.post(f"/v1/buckets/{bucket_id}/archive", headers=headers)
    assert archived.status_code == 200
    assert archived.json()["status"] == "ARCHIVED"
    assert archived.json()["archived_at"] is not None
    assert client.get("/v1/buckets", headers=headers).json() == []
    archived_list = client.get("/v1/buckets/archived", headers=headers)
    assert archived_list.status_code == 200
    assert [bucket["bucket_id"] for bucket in archived_list.json()] == [bucket_id]
    history = client.get(f"/v1/buckets/{bucket_id}/transactions", headers=headers)
    assert history.status_code == 200
    assert len(history.json()) == 3

    restored = client.post(f"/v1/buckets/{bucket_id}/restore", headers=headers)
    assert restored.status_code == 200
    assert restored.json()["status"] == "ACTIVE"
    assert restored.json()["archived_at"] is None

    archived_again = client.post(f"/v1/buckets/{bucket_id}/archive", headers=headers)
    assert archived_again.status_code == 200
    for bucket_number in range(10):
        response = client.post(
            "/v1/buckets",
            headers=headers,
            json={"name": f"New goal {bucket_number + 1}", "target_amount": "100"},
        )
        assert response.status_code == 201

    restore_at_limit = client.post(f"/v1/buckets/{bucket_id}/restore", headers=headers)
    assert restore_at_limit.status_code == 422
