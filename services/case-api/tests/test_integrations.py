"""
CrimeLensAI — Unit Tests for Service Integrations
====================================================
Tests for the AI/NLP and Graph service HTTP clients.

Uses httpx's MockTransport so no real HTTP requests are made.
"""

import json

import httpx
import pytest

from app.core.config import settings
from app.integrations.ai_integration import (
    HTTPAIService,
    MockAIService,
    get_ai_service,
)
from app.integrations.graph_integration import (
    HTTPGraphService,
    MockGraphService,
    get_graph_service,
)


# ============================================================
# Helpers
# ============================================================

def _make_mock_transport(handler):
    """Create an httpx.MockTransport from an async handler function."""
    return httpx.MockTransport(handler)


# ============================================================
# AI / NLP Service Tests
# ============================================================

class TestMockAIService:
    """Tests for the in-process mock NLP implementation."""

    @pytest.mark.asyncio
    async def test_extract_entities_returns_empty(self):
        svc = MockAIService()
        result = await svc.extract_entities("Some FIR text")
        assert "entities" in result
        assert result["entities"] == []

    @pytest.mark.asyncio
    async def test_resolve_entities_returns_empty(self):
        svc = MockAIService()
        result = await svc.resolve_entities([{"value": "John"}])
        assert "resolved_groups" in result
        assert result["resolved_groups"] == []


class TestHTTPAIService:
    """Tests for the real HTTP NLP client using mocked transport."""

    @pytest.mark.asyncio
    async def test_extract_entities_success(self):
        expected_entities = [
            {
                "entity_type": "PERSON",
                "value": "Rajesh Kumar",
                "confidence": 0.95,
                "start_offset": 0,
                "end_offset": 12,
                "source_field": "fir_text",
            }
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/extract"
            body = json.loads(request.content)
            assert body["text"] == "Rajesh Kumar was seen"
            assert body["source_type"] == "fir_text"
            return httpx.Response(200, json={"entities": expected_entities})

        svc = HTTPAIService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.extract_entities("Rajesh Kumar was seen")
        assert result["entities"] == expected_entities
        await svc.close()

    @pytest.mark.asyncio
    async def test_extract_entities_timeout(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        svc = HTTPAIService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        with pytest.raises(httpx.TimeoutException):
            await svc.extract_entities("Some text")
        await svc.close()

    @pytest.mark.asyncio
    async def test_extract_entities_server_error(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"detail": "Internal error"})

        svc = HTTPAIService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        with pytest.raises(httpx.HTTPStatusError):
            await svc.extract_entities("Some text")
        await svc.close()

    @pytest.mark.asyncio
    async def test_resolve_entities_success(self):
        expected_groups = [
            {
                "canonical_value": "Rajesh Kumar",
                "entity_type": "PERSON",
                "variants": [],
                "merge_confidence": 0.9,
            }
        ]

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/resolve"
            body = json.loads(request.content)
            assert "entities" in body
            return httpx.Response(200, json={"resolved_groups": expected_groups})

        svc = HTTPAIService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.resolve_entities([{"value": "Rajesh Kumar"}])
        assert result["resolved_groups"] == expected_groups
        await svc.close()


# ============================================================
# Graph Service Tests
# ============================================================

class TestMockGraphService:
    """Tests for the in-process mock Graph implementation."""

    @pytest.mark.asyncio
    async def test_upsert_entity(self):
        svc = MockGraphService()
        result = await svc.upsert_entity({"entity_type": "PERSON", "value": "Test"})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_create_relationship(self):
        svc = MockGraphService()
        result = await svc.create_relationship({"source_entity_id": "a", "target_entity_id": "b"})
        assert result["status"] == "ok"

    @pytest.mark.asyncio
    async def test_get_cross_case_linkage(self):
        svc = MockGraphService()
        result = await svc.get_cross_case_linkage("case-123")
        assert result["case_id"] == "case-123"
        assert result["linked_cases"] == []

    @pytest.mark.asyncio
    async def test_get_entity_centrality(self):
        svc = MockGraphService()
        result = await svc.get_entity_centrality("entity-456")
        assert result["entity_id"] == "entity-456"

    @pytest.mark.asyncio
    async def test_detect_communities(self):
        svc = MockGraphService()
        result = await svc.detect_communities()
        assert result["communities"] == []

    @pytest.mark.asyncio
    async def test_shortest_path(self):
        svc = MockGraphService()
        result = await svc.shortest_path("a", "b")
        assert result["entity_a"] == "a"
        assert result["entity_b"] == "b"
        assert result["path"] == []


class TestHTTPGraphService:
    """Tests for the real HTTP Graph client using mocked transport."""

    @pytest.mark.asyncio
    async def test_upsert_entity_success(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/entities"
            assert request.method == "POST"
            return httpx.Response(200, json={"status": "ok"})

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.upsert_entity({"entity_type": "PERSON", "value": "Test"})
        assert result["status"] == "ok"
        await svc.close()

    @pytest.mark.asyncio
    async def test_create_relationship_success(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/relationships"
            assert request.method == "POST"
            body = json.loads(request.content)
            assert "source_entity_id" in body
            return httpx.Response(200, json={"status": "ok"})

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.create_relationship({
            "source_entity_id": "a",
            "target_entity_id": "b",
            "relationship_type": "CONTACTED",
            "source_case_id": "case-1",
            "confidence": 0.8,
            "why_linked": "Same phone number",
        })
        assert result["status"] == "ok"
        await svc.close()

    @pytest.mark.asyncio
    async def test_get_cross_case_linkage_success(self):
        expected = {"case_id": "case-1", "linked_cases": []}

        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/linkage/case-1" in str(request.url)
            assert request.method == "GET"
            return httpx.Response(200, json=expected)

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.get_cross_case_linkage("case-1")
        assert result == expected
        await svc.close()

    @pytest.mark.asyncio
    async def test_get_entity_centrality_success(self):
        expected = {"entity_id": "e-1", "centrality": {"degree": 5}}

        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/centrality/e-1" in str(request.url)
            return httpx.Response(200, json=expected)

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.get_entity_centrality("e-1")
        assert result == expected
        await svc.close()

    @pytest.mark.asyncio
    async def test_detect_communities_success(self):
        expected = {"communities": [{"id": 1, "members": ["a", "b"]}]}

        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/api/v1/communities"
            return httpx.Response(200, json=expected)

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.detect_communities()
        assert result == expected
        await svc.close()

    @pytest.mark.asyncio
    async def test_shortest_path_success(self):
        expected = {"entity_a": "a", "entity_b": "b", "path": ["a", "c", "b"]}

        async def handler(request: httpx.Request) -> httpx.Response:
            assert "entity_a=a" in str(request.url)
            assert "entity_b=b" in str(request.url)
            return httpx.Response(200, json=expected)

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        result = await svc.shortest_path("a", "b")
        assert result == expected
        await svc.close()

    @pytest.mark.asyncio
    async def test_server_error_raises(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503, json={"detail": "Unavailable"})

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        with pytest.raises(httpx.HTTPStatusError):
            await svc.upsert_entity({"entity_type": "PERSON"})
        await svc.close()

    @pytest.mark.asyncio
    async def test_timeout_raises(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ReadTimeout("timed out")

        svc = HTTPGraphService()
        svc._client = httpx.AsyncClient(
            base_url="http://test", transport=_make_mock_transport(handler)
        )

        with pytest.raises(httpx.TimeoutException):
            await svc.get_cross_case_linkage("case-1")
        await svc.close()


# ============================================================
# Factory Tests
# ============================================================

class TestFactoryFunctions:
    """Tests for the factory functions that select implementations."""

    def test_get_ai_service_mock(self, monkeypatch):
        monkeypatch.setattr(settings, "integration_mode", "mock")
        svc = get_ai_service()
        assert isinstance(svc, MockAIService)

    def test_get_ai_service_real(self, monkeypatch):
        monkeypatch.setattr(settings, "integration_mode", "real")
        svc = get_ai_service()
        assert isinstance(svc, HTTPAIService)

    def test_get_graph_service_mock(self, monkeypatch):
        monkeypatch.setattr(settings, "integration_mode", "mock")
        svc = get_graph_service()
        assert isinstance(svc, MockGraphService)

    def test_get_graph_service_real(self, monkeypatch):
        monkeypatch.setattr(settings, "integration_mode", "real")
        svc = get_graph_service()
        assert isinstance(svc, HTTPGraphService)
