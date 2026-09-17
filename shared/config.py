from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    service_name: str = "savings-bucket-service"
    database_url: str = (
        "postgresql+psycopg://savings:savings@localhost:5432/savings_bucket"
    )
    jwt_issuer: str = "http://localhost:8080/realms/savings-bucket"
    jwt_audience: str = "savings-bucket-local"
    banking_adapter_mode: str = "mock"
    event_bus_mode: str = "local"
    sqs_mode: str = "local"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
