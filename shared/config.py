from functools import lru_cache
from urllib.parse import quote

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"
    log_level: str = "INFO"
    service_name: str = "savings-bucket-service"
    database_url: str = ""
    database_user: str = "dnyanesh_kudale"
    database_password: str = Field(default="", validation_alias="FDE_DB_PASS")
    jwt_issuer: str = "http://localhost:8080/realms/savings-bucket"
    jwt_audience: str = "savings-bucket-local"
    banking_adapter_mode: str = "mock"
    event_bus_mode: str = "local"
    sqs_mode: str = "local"
    bucket_service_url: str = "http://localhost:8001"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def build_local_database_url(self) -> "Settings":
        if not self.database_url and self.database_password:
            self.database_url = (
                "postgresql://"
                f"{self.database_user}:{quote(self.database_password, safe='')}"
                "@localhost:5432/savings_bucket"
            )
        elif self.database_url.startswith("postgresql+psycopg://"):
            self.database_url = self.database_url.replace(
                "postgresql+psycopg://", "postgresql://", 1
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
