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
