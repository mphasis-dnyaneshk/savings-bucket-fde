from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi.testclient import TestClient

from services.ai_advisor_service.main import app as ai_advisor_app
from services.ai_advisor_service.schemas import AdvisorResponse


def test_goal_adjustment_uses_customer_bucket_and_computed_projection(
    monkeypatch,
) -> None:
    bucket_id = uuid4()
    snapshot = {
        "buckets": [
            {
                "bucket_id": str(bucket_id),
                "name": "Emergency fund",
                "target_amount": "1000.00",
                "current_balance": "400.00",
                "remaining_amount": "600.00",
                "target_date": "2027-10-01",
                "status": "ACTIVE",
            }
        ],
        "monthly_activity": [],
    }
    captured = {}

    monkeypatch.setattr(
        "services.ai_advisor_service.main.fetch_customer_snapshot",
        lambda database_url, customer_id: snapshot,
    )

    def fake_advice(feature, data, region, model_id, user_input=None):
        captured.update(
            feature=feature,
            data=data,
            user_input=user_input,
        )
        return AdvisorResponse(
            summary="The target is progressing.",
            recommendations=[{"title": "Review", "detail": "Check the target date."}],
        )

    monkeypatch.setattr("services.ai_advisor_service.main.generate_advice", fake_advice)
    ai_advisor_app.state.settings.database_url = "postgresql://local/test"
    ai_advisor_app.state.settings.bedrock_model_id = "test-model"

    response = TestClient(ai_advisor_app).post(
        "/v1/ai/goal-adjustments",
        headers={"X-Customer-ID": "customer-1"},
        json={"bucket_id": str(bucket_id), "monthly_contribution": "100"},
    )

    assert response.status_code == 200
    assert response.json()["remaining_amount"] == "600.00"
    assert response.json()["projected_months_at_contribution"] == 6
    assert response.json()["target_date"] == date(2027, 10, 1).isoformat()
    assert captured["feature"] == "intelligent_goal_adjustment"
    assert captured["user_input"]["monthly_contribution"] == "100"


def test_bucket_and_savings_recommendations_use_customer_snapshot(monkeypatch) -> None:
    customer_ids = []
    features = []

    def fake_snapshot(database_url, customer_id):
        customer_ids.append(customer_id)
        return {"buckets": [], "monthly_activity": []}

    def fake_advice(feature, snapshot, region, model_id, user_input=None):
        features.append(feature)
        return AdvisorResponse(
            summary="Start with a practical savings goal.",
            recommendations=[
                {
                    "title": "Choose a priority",
                    "detail": "Consider your near-term goals.",
                }
            ],
        )

    monkeypatch.setattr(
        "services.ai_advisor_service.main.fetch_customer_snapshot", fake_snapshot
    )
    monkeypatch.setattr("services.ai_advisor_service.main.generate_advice", fake_advice)
    ai_advisor_app.state.settings.database_url = "postgresql://local/test"
    ai_advisor_app.state.settings.bedrock_model_id = "test-model"
    client = TestClient(ai_advisor_app)
    headers = {"X-Customer-ID": "customer-2"}

    buckets = client.post(
        "/v1/ai/bucket-recommendations",
        headers=headers,
        json={"priorities": ["emergency fund"]},
    )
    savings = client.post(
        "/v1/ai/savings-recommendations",
        headers=headers,
        json={"monthly_savings_budget": "250"},
    )

    assert buckets.status_code == 200
    assert savings.status_code == 200
    assert customer_ids == ["customer-2", "customer-2"]
    assert features == [
        "smart_bucket_recommendation",
        "personal_savings_recommendation",
    ]


def test_ai_endpoints_require_customer_id() -> None:
    response = TestClient(ai_advisor_app).post("/v1/ai/bucket-recommendations", json={})

    assert response.status_code == 401


def test_bedrock_converse_parses_valid_advice(monkeypatch) -> None:
    from services.ai_advisor_service import bedrock

    class FakeClient:
        def converse(self, **kwargs):
            assert kwargs["modelId"] == "test-model"
            return {
                "output": {
                    "message": {
                        "content": [
                            {
                                "text": (
                                    '{"summary":"On track.","recommendations":'
                                    '[{"title":"Keep going","detail":"Continue regularly."}],'
                                    '"disclaimer":"Informational only."}'
                                )
                            }
                        ]
                    }
                }
            }

    monkeypatch.setattr(bedrock.boto3, "client", lambda *args, **kwargs: FakeClient())

    result = bedrock.generate_advice(
        "personal_savings_recommendation",
        {"buckets": []},
        "us-east-1",
        "test-model",
    )

    assert result.summary == "On track."
    assert result.recommendations[0].title == "Keep going"
