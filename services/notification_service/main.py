from fastapi import FastAPI

from shared.app import create_app


def register_routes(app: FastAPI) -> None:
    @app.get("/internal/status")
    async def status() -> dict[str, str]:
        return {"status": "ready", "mode": "local-noop"}


app = create_app("notification-service", register_routes)
