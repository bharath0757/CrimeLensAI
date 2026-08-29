"""
CrimeLensAI — Graph Service Integration
==========================================
HTTP client for communicating with the deployed Graph (Neo4j) service.

Endpoints consumed:
  POST /api/v1/entities                — Upsert entity node
  POST /api/v1/relationships           — Create relationship
  GET  /api/v1/linkage/{case_id}       — Cross-case linkage
  GET  /api/v1/centrality/{entity_id}  — Centrality metrics
  GET  /api/v1/communities             — Community detection
  GET  /api/v1/shortest-path           — Shortest path

The mock implementation returns empty results and is used for local
development and testing when the Graph service is unavailable.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


# ---- Abstract interface ----

class GraphServiceBase(ABC):
    """Interface for Graph service integration."""

    @abstractmethod
    async def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """Create or update an entity node in the graph."""

    @abstractmethod
    async def create_relationship(
        self, relationship: dict[str, Any]
    ) -> dict[str, Any]:
        """Create a relationship between two entity nodes."""

    @abstractmethod
    async def get_cross_case_linkage(
        self, case_id: str
    ) -> dict[str, Any]:
        """Find all cases linked through shared entities."""

    @abstractmethod
    async def get_entity_centrality(
        self, entity_id: str
    ) -> dict[str, Any]:
        """Compute centrality metrics for an entity node."""

    @abstractmethod
    async def detect_communities(self) -> dict[str, Any]:
        """Run community detection on the entity graph."""

    @abstractmethod
    async def shortest_path(
        self, entity_a: str, entity_b: str
    ) -> dict[str, Any]:
        """Find the shortest path between two entities."""


# ---- Mock implementation ----

class MockGraphService(GraphServiceBase):
    """
    In-process mock that returns placeholder results.
    Useful for local development and testing without the Graph service.
    """

    async def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        logger.debug("MockGraphService.upsert_entity called")
        return {"status": "ok", "message": "Entity upsert placeholder"}

    async def create_relationship(
        self, relationship: dict[str, Any]
    ) -> dict[str, Any]:
        logger.debug("MockGraphService.create_relationship called")
        return {"status": "ok", "message": "Relationship creation placeholder"}

    async def get_cross_case_linkage(
        self, case_id: str
    ) -> dict[str, Any]:
        logger.debug("MockGraphService.get_cross_case_linkage called")
        return {
            "case_id": case_id,
            "linked_cases": [],
            "message": "Cross-case linkage placeholder",
        }

    async def get_entity_centrality(
        self, entity_id: str
    ) -> dict[str, Any]:
        logger.debug("MockGraphService.get_entity_centrality called")
        return {
            "entity_id": entity_id,
            "centrality": {},
            "message": "Centrality analysis placeholder",
        }

    async def detect_communities(self) -> dict[str, Any]:
        logger.debug("MockGraphService.detect_communities called")
        return {"communities": [], "message": "Community detection placeholder"}

    async def shortest_path(
        self, entity_a: str, entity_b: str
    ) -> dict[str, Any]:
        logger.debug("MockGraphService.shortest_path called")
        return {
            "entity_a": entity_a,
            "entity_b": entity_b,
            "path": [],
            "explanation": "Shortest path placeholder",
        }


# ---- Real HTTP implementation ----

class HTTPGraphService(GraphServiceBase):
    """
    Real async HTTP client that calls the deployed Graph service.

    Uses httpx.AsyncClient with connection pooling and configurable timeouts.
    Does NOT fail at startup if the Graph service is unreachable.
    """

    def __init__(self) -> None:
        self._base_url = settings.graph_service_url.rstrip("/")
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

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """
        Make a request to the Graph service with error handling.
        """
        client = self._get_client()
        try:
            response = await client.request(
                method, path, json=json, params=params
            )
            response.raise_for_status()
            return response.json()
        except httpx.TimeoutException:
            logger.error("Graph service timeout on %s %s", method, path)
            raise
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Graph service returned %s on %s %s: %s",
                exc.response.status_code,
                method,
                path,
                exc.response.text[:500],
            )
            raise
        except httpx.ConnectError:
            logger.error(
                "Cannot connect to Graph service at %s", self._base_url
            )
            raise

    async def upsert_entity(self, entity: dict[str, Any]) -> dict[str, Any]:
        """POST /api/v1/entities"""
        return await self._request("POST", "/api/v1/entities", json=entity)

    async def create_relationship(
        self, relationship: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /api/v1/relationships"""
        return await self._request(
            "POST", "/api/v1/relationships", json=relationship
        )

    async def get_cross_case_linkage(
        self, case_id: str
    ) -> dict[str, Any]:
        """GET /api/v1/linkage/{case_id}"""
        return await self._request("GET", f"/api/v1/linkage/{case_id}")

    async def get_entity_centrality(
        self, entity_id: str
    ) -> dict[str, Any]:
        """GET /api/v1/centrality/{entity_id}"""
        return await self._request("GET", f"/api/v1/centrality/{entity_id}")

    async def detect_communities(self) -> dict[str, Any]:
        """GET /api/v1/communities"""
        return await self._request("GET", "/api/v1/communities")

    async def shortest_path(
        self, entity_a: str, entity_b: str
    ) -> dict[str, Any]:
        """GET /api/v1/shortest-path?entity_a=...&entity_b=..."""
        return await self._request(
            "GET",
            "/api/v1/shortest-path",
            params={"entity_a": entity_a, "entity_b": entity_b},
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()


# ---- Factory ----

def get_graph_service() -> GraphServiceBase:
    """
    Return the appropriate Graph service implementation based on configuration.

    INTEGRATION_MODE=real  → HTTPGraphService (live HTTP calls)
    INTEGRATION_MODE=mock  → MockGraphService (in-process stubs)
    """
    if settings.use_real_integrations:
        logger.info(
            "Using real Graph service at %s", settings.graph_service_url
        )
        return HTTPGraphService()
    logger.info("Using mock Graph service")
    return MockGraphService()
