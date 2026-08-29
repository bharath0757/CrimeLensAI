"""
CrimeLensAI — AI / NLP Service Integration
=============================================
HTTP client for communicating with the deployed NLP (entity-extraction) service.

Endpoints consumed:
  POST /api/v1/extract   — Extract entities from raw text
  POST /api/v1/resolve   — Resolve entity variants

The mock implementation returns empty results and is used for local
development and testing when the NLP service is unavailable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---- Abstract interface ----

class AIServiceBase(ABC):
    """Interface for AI/NLP service integration."""

    @abstractmethod
    async def extract_entities(
        self, text: str, source_type: str = "fir_text"
    ) -> dict[str, Any]:
        """Extract entities from raw text."""

    @abstractmethod
    async def resolve_entities(
        self, entities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Resolve entity variants into canonical groups."""


# ---- Mock implementation ----

class MockAIService(AIServiceBase):
    """
    In-process mock that returns empty results.
    Useful for local development and testing without the NLP service.
    """

    async def extract_entities(
        self, text: str, source_type: str = "fir_text"
    ) -> dict[str, Any]:
        logger.debug("MockAIService.extract_entities called")
        return {"entities": []}

    async def resolve_entities(
        self, entities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        logger.debug("MockAIService.resolve_entities called")
        return {"resolved_groups": []}


# ---- Real HTTP implementation ----

class HTTPAIService(AIServiceBase):
    """
    Real async HTTP client that calls the deployed NLP service.

    Uses httpx.AsyncClient with connection pooling and configurable timeouts.
    Does NOT fail at startup if the NLP service is unreachable.
    """

    def __init__(self) -> None:
        self._base_url = settings.ai_service_url.rstrip("/")
        self._timeout = httpx.Timeout(
            connect=settings.http_connect_timeout,
            read=settings.http_read_timeout,
            write=settings.http_read_timeout,
            pool=settings.http_connect_timeout,
        )
        self._client: httpx.AsyncClient | None = None

    def _get_client(self) -> httpx.AsyncClient:
        """Lazy-initialize the HTTP client (no startup dependency)."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self._base_url,
                timeout=self._timeout,
            )
        return self._client

    async def extract_entities(
        self, text: str, source_type: str = "fir_text"
    ) -> dict[str, Any]:
        """
        POST /api/v1/extract

        Request:  { "text": "...", "source_type": "fir_text" }
        Response: { "entities": [...] }
        """
        client = self._get_client()
        # Fix: ensure we don't duplicate /api/v1 if AI_SERVICE_URL already includes it
        path = "/extract" if self._base_url.endswith("/api/v1") else "/api/v1/extract"
        try:
            response = await client.post(
                path,
                json={"text": text, "source_type": source_type},
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("NLP service timeout on /api/v1/extract")
            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "NLP service returned %s on /api/v1/extract: %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise
        except httpx.ConnectError:
            logger.error(
                "Cannot connect to NLP service at %s", self._base_url
            )
            raise

    async def resolve_entities(
        self, entities: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        POST /api/v1/resolve

        Request:  { "entities": [...] }
        Response: { "resolved_groups": [...] }
        """
        client = self._get_client()
        # Fix: ensure we don't duplicate /api/v1 if AI_SERVICE_URL already includes it
        path = "/resolve" if self._base_url.endswith("/api/v1") else "/api/v1/resolve"
        try:
            response = await client.post(
                path,
                json={"entities": entities},
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("NLP service timeout on /api/v1/resolve")
            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "NLP service returned %s on /api/v1/resolve: %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise
        except httpx.ConnectError:
            logger.error(
                "Cannot connect to NLP service at %s", self._base_url
            )
            raise

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# ---- Factory ----

def get_ai_service() -> AIServiceBase:
    """
    Return the appropriate AI service implementation based on configuration.

    INTEGRATION_MODE=real  → HTTPAIService (live HTTP calls)
    INTEGRATION_MODE=mock  → MockAIService (in-process stubs)
    """
    if settings.use_real_integrations:
        logger.info(
            "Using real NLP service at %s", settings.ai_service_url
        )
        return HTTPAIService()
    logger.info("Using mock NLP service")
    return MockAIService()
