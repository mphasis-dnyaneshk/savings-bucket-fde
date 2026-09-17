from fastapi.testclient import TestClient

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
