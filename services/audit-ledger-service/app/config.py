"""Deployment configuration for the internal audit service."""

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    LEDGER_DATABASE_URL: str = ""
    MIGRATION_DATABASE_URL: str = ""
    LEDGER_DATABASE_PASSWORD: str = ""
    SERVICE_AUTH_TOKEN: str = ""
    ENVIRONMENT: str = "development"
    LEDGER_AUTO_MIGRATE: bool = True
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    def validate_runtime(self) -> None:
        if not self.LEDGER_DATABASE_URL and self.MIGRATION_DATABASE_URL and self.LEDGER_DATABASE_PASSWORD:
            migration_url = make_url(self.MIGRATION_DATABASE_URL)
            self.LEDGER_DATABASE_URL = migration_url.set(
                drivername="postgresql+psycopg2",
                username="crimelens_ledger",
                password=self.LEDGER_DATABASE_PASSWORD,
            ).render_as_string(hide_password=False)
        if len(self.SERVICE_AUTH_TOKEN.encode()) < 32:
            raise ValueError("SERVICE_AUTH_TOKEN must contain at least 32 bytes")
        if not self.LEDGER_DATABASE_URL:
            raise ValueError("LEDGER_DATABASE_URL must be configured")
        if self.ENVIRONMENT == "production" and not self.LEDGER_DATABASE_URL.startswith("postgresql"):
            raise ValueError("Production audit storage requires PostgreSQL")
        if self.ENVIRONMENT == "production" and self.LEDGER_AUTO_MIGRATE:
            raise ValueError("Production ledger runtime cannot own or migrate its schema")
