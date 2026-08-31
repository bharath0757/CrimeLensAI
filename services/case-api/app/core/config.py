import os
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "CrimeLens AI Backend"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True

    # Security & Auth Configuration
    SECRET_KEY: str = "CRIMELENS_AI_SECRET_KEY_SUPER_SECURE_STUDENT_SIH_TOKEN_2026"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    ALLOWED_ORIGINS: List[str] = [
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
    ALLOWED_EXTENSIONS: List[str] = ["pdf", "txt", "docx", "png", "jpg", "jpeg", "csv", "json", "log"]

    # External Integration Endpoints
    ai_service_url: str = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
    graph_service_url: str = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8002")

    # ---- HTTP client settings ----
    http_connect_timeout: float = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5.0"))
    http_read_timeout: float = float(os.getenv("HTTP_READ_TIMEOUT", "30.0"))

    integration_mode: str = os.getenv("INTEGRATION_MODE", "mock")

    @property
    def use_real_integrations(self) -> bool:
        return self.integration_mode.lower() == "real"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
