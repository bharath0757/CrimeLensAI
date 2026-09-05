import os
import secrets
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


def _http_service_url(value: str) -> str:
    """Accept Render's private `host:port` references as well as full URLs."""
    value = value.strip().rstrip("/")
    if value and "://" not in value:
        return f"http://{value}"
    return value


class Settings(BaseSettings):
    PROJECT_NAME: str = "CrimeLens AI Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False
    ENVIRONMENT: Literal["development", "test", "production"] = "development"

    # Security & Auth Configuration
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(48))
    ALGORITHM: Literal["HS256"] = "HS256"
    JWT_ISSUER: str = "crimelens-case-api"
    JWT_AUDIENCE: str = "crimelens-officer"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, ge=1, le=1440)

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:4173",
        "http://127.0.0.1:4173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # File Upload Settings
    UPLOAD_DIR: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")
    MAX_FILE_SIZE_BYTES: int = 50 * 1024 * 1024  # 50 MB
    ALLOWED_EXTENSIONS: list[str] = ["pdf", "txt", "docx", "png", "jpg", "jpeg", "csv", "json", "log"]

    # External Integration Endpoints
    AI_SERVICE_URL: str = "http://extraction:8001"
    GRAPH_SERVICE_URL: str = "http://graph:8002"
    LEDGER_SERVICE_URL: str = "http://ledger:8003"
    SERVICE_AUTH_TOKEN: str = ""
    INGESTION_SERVICE_URL: str = "http://ingestion:8004"
    DATA_BACKEND: str = "memory"
    DATABASE_URL: str = ""
    MIGRATION_DATABASE_URL: str = ""
    API_DATABASE_PASSWORD: str = ""

    @model_validator(mode="after")
    def production_security(self):
        self.AI_SERVICE_URL = _http_service_url(self.AI_SERVICE_URL)
        self.GRAPH_SERVICE_URL = _http_service_url(self.GRAPH_SERVICE_URL)
        self.LEDGER_SERVICE_URL = _http_service_url(self.LEDGER_SERVICE_URL)
        self.INGESTION_SERVICE_URL = _http_service_url(self.INGESTION_SERVICE_URL)
        if (
            self.DATA_BACKEND == "postgres"
            and not self.DATABASE_URL
            and self.MIGRATION_DATABASE_URL
            and self.API_DATABASE_PASSWORD
        ):
            migration_url = make_url(self.MIGRATION_DATABASE_URL)
            self.DATABASE_URL = migration_url.set(
                drivername="postgresql+psycopg2",
                username="crimelens_api",
                password=self.API_DATABASE_PASSWORD,
            ).render_as_string(hide_password=False)
        if self.ENVIRONMENT == "production":
            if "SECRET_KEY" not in self.model_fields_set or len(self.SECRET_KEY.encode()) < 32:
                raise ValueError("Production requires an explicit SECRET_KEY of at least 32 bytes")
            if self.DATA_BACKEND != "postgres":
                raise ValueError("Production requires PostgreSQL, not the seeded in-memory demo")
            if len(self.SERVICE_AUTH_TOKEN.encode()) < 32:
                raise ValueError("Production requires SERVICE_AUTH_TOKEN of at least 32 bytes")
            if not self.DATABASE_URL.startswith("postgresql"):
                raise ValueError("Production requires a PostgreSQL DATABASE_URL")
            if not all(
                (self.AI_SERVICE_URL, self.GRAPH_SERVICE_URL, self.LEDGER_SERVICE_URL, self.INGESTION_SERVICE_URL)
            ):
                raise ValueError("Production requires all internal service URLs")
            if self.DEBUG or "*" in self.ALLOWED_ORIGINS:
                raise ValueError("Production cannot enable DEBUG or wildcard CORS")
        return self

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
