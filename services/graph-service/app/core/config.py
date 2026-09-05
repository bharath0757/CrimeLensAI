from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    NEO4J_URI: str = "bolt://neo4j:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = ""
    GRAPH_BACKEND: Literal["memory", "neo4j"] = "memory"
    SERVICE_AUTH_TOKEN: str = ""
    SERVICE_NAME: str = "graph"
    SERVICE_VERSION: str = "0.1.0"

    @model_validator(mode="after")
    def production_security(self):
        if self.ENVIRONMENT == "production":
            if self.GRAPH_BACKEND != "neo4j":
                raise ValueError("Production graph service requires the Neo4j backend")
            if not self.NEO4J_URI or not self.NEO4J_USER or len(self.NEO4J_PASSWORD) < 12:
                raise ValueError("Production graph service requires Neo4j credentials")
            if len(self.SERVICE_AUTH_TOKEN.encode()) < 32:
                raise ValueError("Production graph service requires a 32-byte service token")
        return self

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=True)


@lru_cache
def get_settings() -> Settings:
    return Settings()
