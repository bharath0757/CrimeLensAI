"""
CrimeLensAI — API Service Configuration
==========================================
Environment-driven settings for the Case API / orchestration layer.

All downstream service URLs default to localhost for local development.
In production (Cloud Run), set AI_SERVICE_URL and GRAPH_SERVICE_URL
as environment variables.
"""

import os


class Settings:
    """Application settings loaded from environment variables."""

    # ---- Downstream service URLs ----
    ai_service_url: str = os.getenv("AI_SERVICE_URL", "http://localhost:8001")
    graph_service_url: str = os.getenv("GRAPH_SERVICE_URL", "http://localhost:8002")

    # ---- HTTP client settings ----
    # Timeout for connecting to downstream services (seconds)
    http_connect_timeout: float = float(os.getenv("HTTP_CONNECT_TIMEOUT", "5.0"))
    # Timeout for reading a response from downstream services (seconds)
    http_read_timeout: float = float(os.getenv("HTTP_READ_TIMEOUT", "30.0"))

    # ---- Integration mode ----
    # When "real", use live HTTP clients to downstream services.
    # When "mock", use in-process mock implementations (default for local dev).
    integration_mode: str = os.getenv("INTEGRATION_MODE", "mock")

    @property
    def use_real_integrations(self) -> bool:
        """Return True when integration mode is set to 'real'."""
        return self.integration_mode.lower() == "real"


settings = Settings()
