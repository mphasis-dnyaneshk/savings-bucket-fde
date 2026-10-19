import json
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from pydantic import ValidationError

from services.ai_advisor_service.schemas import AdvisorResponse

logger = logging.getLogger(__name__)


class BedrockNotConfigured(Exception):
    pass


class BedrockUnavailable(Exception):
    pass


def generate_advice(
    feature: str,
    snapshot: dict,
    region: str,
    model_id: str,
    user_input: dict | None = None,
) -> AdvisorResponse:
    if not model_id:
        raise BedrockNotConfigured("Set BEDROCK_MODEL_ID to enable AI advice.")

    system_prompt = (
        "You are a cautious savings-planning assistant. Use only the supplied bucket and "
        "transaction data. Do not assume income, expenses, debt, or financial goals that "
        "are not supplied. Do not give investment, tax, credit, or banking advice. "
        "Never claim to change a bucket or move money. Do not invent calculations; "
        "explain suggestions qualitatively and ground each one in the supplied data. "
        "Return only a JSON object with summary (string), recommendations (array of "
        "objects with title and detail strings), and disclaimer (string)."
    )
    request = {
        "feature": feature,
        "customer_data": snapshot,
        "customer_preferences": user_input or {},
    }

    try:
        response = boto3.client("bedrock-runtime", region_name=region).converse(
            modelId=model_id,
            system=[{"text": system_prompt}],
            messages=[{"role": "user", "content": [{"text": json.dumps(request)}]}],
            inferenceConfig={"maxTokens": 700, "temperature": 0.2},
        )
        text = "".join(
            item.get("text", "") for item in response["output"]["message"]["content"]
        )
        return AdvisorResponse.model_validate_json(text)
    except ClientError as error:
        error_code = error.response.get("Error", {}).get("Code", "UnknownClientError")
        logger.warning("Bedrock Converse request failed with %s", error_code)
        raise BedrockUnavailable(
            f"Bedrock Converse request failed: {error_code}."
        ) from error
    except BotoCoreError as error:
        error_type = type(error).__name__
        logger.warning("Bedrock SDK request failed with %s", error_type)
        raise BedrockUnavailable(
            f"Bedrock SDK request failed: {error_type}."
        ) from error
    except ValidationError as error:
        logger.warning("Bedrock response did not match the advisor response schema")
        raise BedrockUnavailable(
            "Bedrock returned a response that did not match the expected JSON schema."
        ) from error
    except (KeyError, TypeError) as error:
        logger.warning(
            "Bedrock response had an unexpected structure (%s)", type(error).__name__
        )
        raise BedrockUnavailable(
            "Bedrock returned a response with an unexpected structure."
        ) from error
