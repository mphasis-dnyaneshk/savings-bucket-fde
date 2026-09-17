from collections.abc import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.config import Settings, get_settings


def create_app(
    service_name: str, register_routes: Callable[[FastAPI], None] | None = None
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=f"Savings Bucket {service_name}", version="0.1.0")
    app.state.settings = settings

    @app.middleware("http")
    async def correlation_id(request: Request, call_next):
        request_id = request.headers.get("X-Correlation-ID", "local-request")
        response = await call_next(request)
        response.headers["X-Correlation-ID"] = request_id
        return response

    @app.get("/health/live", tags=["health"])
    async def liveness() -> dict[str, str]:
        return {"status": "ok", "service": service_name}

    @app.get("/health/ready", tags=["health"])
    async def readiness() -> dict[str, str]:
        return {
            "status": "ok",
            "service": service_name,
            "environment": settings.app_env,
        }

    @app.exception_handler(Exception)
    async def unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": "An unexpected error occurred.",
                "correlationId": request.headers.get(
                    "X-Correlation-ID", "local-request"
                ),
            },
        )

    if register_routes:
        register_routes(app)

    return app
