from fastapi import HTTPException


def not_implemented(feature: str) -> HTTPException:
    return HTTPException(
        status_code=501,
        detail=f"{feature} is not implemented in the foundation scaffold.",
    )
