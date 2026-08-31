"""
Comprehensive test suite for the Case API.

Covers:
  - Case CRUD (create, list, get, update, delete)
  - NLP orchestration (mock NLP returns entities → persisted)
  - Downstream failure handling (NLP/Graph fail → case preserved)
  - Dashboard stats
  - Search
  - Health endpoint
"""

import pytest
import pytest
import httpx
from unittest.mock import patch, AsyncMock

from app.api import routes


# ════════════════════════════════════════════════════════════
# Case CRUD
# ════════════════════════════════════════════════════════════


class TestCreateCase:
    """POST /api/v1/cases"""

    def test_create_minimal(self, client):
        resp = client.post("/api/v1/cases", json={"title": "Test Case"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Test Case"
        assert data["status"] == "DRAFT"
        assert "id" in data
        assert data["entities"] == []

    def test_create_with_fir_text(self, client, sample_fir_payload):
        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Robbery at Bank"
        assert data["district"] == "Mumbai Suburban"
        assert data["station"] == "Andheri"
        assert data["id"] is not None

    def test_create_missing_title(self, client):
        resp = client.post("/api/v1/cases", json={})
        assert resp.status_code == 422

    def test_create_generates_unique_ids(self, client):
        r1 = client.post("/api/v1/cases", json={"title": "Case A"})
        r2 = client.post("/api/v1/cases", json={"title": "Case B"})
        assert r1.json()["id"] != r2.json()["id"]


class TestListCases:
    """GET /api/v1/cases"""

    def test_list_empty(self, client):
        resp = client.get("/api/v1/cases")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_list_after_create(self, client):
        client.post("/api/v1/cases", json={"title": "Case 1"})
        client.post("/api/v1/cases", json={"title": "Case 2"})
        resp = client.get("/api/v1/cases")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    def test_list_pagination(self, client):
        for i in range(5):
            client.post("/api/v1/cases", json={"title": f"Case {i}"})
        resp = client.get("/api/v1/cases?skip=2&limit=2")
        assert resp.status_code == 200
        assert len(resp.json()) == 2


class TestGetCase:
    """GET /api/v1/cases/{case_id}"""

    def test_get_existing(self, client):
        create = client.post("/api/v1/cases", json={"title": "My Case"})
        case_id = create.json()["id"]
        resp = client.get(f"/api/v1/cases/{case_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "My Case"

    def test_get_not_found(self, client):
        resp = client.get("/api/v1/cases/nonexistent-id")
        assert resp.status_code == 404


class TestUpdateCase:
    """PUT /api/v1/cases/{case_id}"""

    def test_update_title(self, client):
        create = client.post("/api/v1/cases", json={"title": "Original"})
        case_id = create.json()["id"]
        resp = client.put(
            f"/api/v1/cases/{case_id}",
            json={"title": "Updated"},
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Updated"

    def test_update_not_found(self, client):
        resp = client.put(
            "/api/v1/cases/nonexistent",
            json={"title": "XXX"},
        )
        assert resp.status_code == 404

    def test_update_preserves_other_fields(self, client, sample_fir_payload):
        create = client.post("/api/v1/cases", json=sample_fir_payload)
        case_id = create.json()["id"]
        client.put(
            f"/api/v1/cases/{case_id}",
            json={"district": "Thane"},
        )
        resp = client.get(f"/api/v1/cases/{case_id}")
        data = resp.json()
        assert data["district"] == "Thane"
        assert data["title"] == "Robbery at Bank"  # unchanged


class TestDeleteCase:
    """DELETE /api/v1/cases/{case_id}"""

    def test_delete_soft(self, client):
        create = client.post("/api/v1/cases", json={"title": "To Delete"})
        case_id = create.json()["id"]
        resp = client.delete(f"/api/v1/cases/{case_id}")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ARCHIVED"

        # Case still exists but is ARCHIVED
        get_resp = client.get(f"/api/v1/cases/{case_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["status"] == "ARCHIVED"

    def test_delete_not_found(self, client):
        resp = client.delete("/api/v1/cases/nonexistent")
        assert resp.status_code == 404


# ════════════════════════════════════════════════════════════
# NLP Orchestration
# ════════════════════════════════════════════════════════════


class TestNLPOrchestration:
    """POST /api/v1/cases with NLP extraction integration."""

    def test_nlp_extracts_entities(self, client, sample_fir_payload, mock_nlp_entities):
        """When NLP succeeds, entities should be persisted on the case."""
        # Patch the ai_service to return mock entities
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(return_value=mock_nlp_entities)
        routes.ai_service = mock_ai

        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["entities"]) == 2
        assert data["entities"][0]["entity_type"] == "PERSON"
        assert data["entities"][1]["entity_type"] == "PHONE"
        assert data["processing_notes"] is not None
        assert "NLP: extracted 2 entities" in data["processing_notes"]

    def test_nlp_entities_have_case_id(self, client, sample_fir_payload, mock_nlp_entities):
        """Extracted entities should be stamped with the case ID."""
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(return_value=mock_nlp_entities)
        routes.ai_service = mock_ai

        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        data = resp.json()
        case_id = data["id"]
        for ent in data["entities"]:
            assert ent["case_id"] == case_id

    def test_case_status_progresses(self, client, sample_fir_payload, mock_nlp_entities):
        """Case should move from DRAFT → PROCESSING → ACTIVE."""
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(return_value=mock_nlp_entities)
        mock_graph = AsyncMock()
        mock_graph.upsert_entity = AsyncMock(return_value={"status": "ok"})
        routes.ai_service = mock_ai
        routes.graph_service = mock_graph

        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        data = resp.json()
        # Graph mock succeeded → status should be ACTIVE
        assert data["status"] == "ACTIVE"


class TestDownstreamFailure:
    """Case creation should survive NLP and Graph failures."""

    def test_nlp_failure_case_still_created(self, client, sample_fir_payload):
        """When NLP fails, case should still be created with DRAFT status."""
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(
            side_effect=Exception("NLP service unavailable")
        )
        routes.ai_service = mock_ai

        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] is not None
        assert data["status"] == "DRAFT"
        assert "NLP: extraction failed" in data["processing_notes"]
        assert data["entities"] == []

    def test_graph_failure_entities_preserved(
        self, client, sample_fir_payload, mock_nlp_entities
    ):
        """When Graph fails, entities should still be saved."""
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(return_value=mock_nlp_entities)
        mock_graph = AsyncMock()
        mock_graph.upsert_entity = AsyncMock(
            side_effect=Exception("Graph service unavailable")
        )
        routes.ai_service = mock_ai
        routes.graph_service = mock_graph

        resp = client.post("/api/v1/cases", json=sample_fir_payload)
        assert resp.status_code == 201
        data = resp.json()
        assert len(data["entities"]) == 2
        assert data["status"] == "PROCESSING"  # didn't advance to ACTIVE
        assert "Graph: ingestion failed" in data["processing_notes"]

    def test_no_text_no_nlp_call(self, client):
        """When no fir_text, NLP should not be called."""
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock()
        routes.ai_service = mock_ai

        resp = client.post("/api/v1/cases", json={"title": "Empty Case"})
        assert resp.status_code == 201
        mock_ai.extract_entities.assert_not_called()


class TestDiagnosticEndpoint:
    """GET /api/v1/diagnostics/nlp"""

    def test_diagnostics_success(self, client):
        from app.core.config import settings
        
        async def handler(request: httpx.Request) -> httpx.Response:
            assert "/api/v1/extract" in str(request.url)
            return httpx.Response(200, text="success")

        with patch("httpx.AsyncClient", autospec=True) as MockClient:
            mock_client = AsyncMock()
            mock_client.post.return_value = httpx.Response(200, text="success")
            # We need to mock the async context manager
            MockClient.return_value.__aenter__.return_value = mock_client
            
            resp = client.get("/api/v1/diagnostics/nlp")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status_code"] == 200
            assert data["response_body"] == "success"

    def test_diagnostics_error(self, client):
        with patch("httpx.AsyncClient", autospec=True) as MockClient:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.ConnectError("Connection failed")
            MockClient.return_value.__aenter__.return_value = mock_client
            
            resp = client.get("/api/v1/diagnostics/nlp")
            assert resp.status_code == 200
            data = resp.json()
            assert data["error_type"] == "ConnectError"


# ════════════════════════════════════════════════════════════
# Dashboard Stats
# ════════════════════════════════════════════════════════════


class TestDashboardStats:
    """GET /api/v1/dashboard/stats"""

    def test_empty_dashboard(self, client):
        resp = client.get("/api/v1/dashboard/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 0
        assert data["total_entities"] == 0

    def test_dashboard_after_cases(self, client, sample_fir_payload, mock_nlp_entities):
        mock_ai = AsyncMock()
        mock_ai.extract_entities = AsyncMock(return_value=mock_nlp_entities)
        routes.ai_service = mock_ai

        client.post("/api/v1/cases", json=sample_fir_payload)
        client.post("/api/v1/cases", json={"title": "Case 2"})

        resp = client.get("/api/v1/dashboard/stats")
        data = resp.json()
        assert data["total_cases"] == 2
        assert data["total_entities"] == 2  # from NLP extraction
        assert "DRAFT" in data["cases_by_status"] or "ACTIVE" in data["cases_by_status"]


# ════════════════════════════════════════════════════════════
# Search
# ════════════════════════════════════════════════════════════


class TestSearch:
    """GET /api/v1/search"""

    def test_search_by_title(self, client):
        client.post("/api/v1/cases", json={"title": "Robbery at Bank"})
        client.post("/api/v1/cases", json={"title": "Kidnapping Case"})
        resp = client.get("/api/v1/search?q=Robbery")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 1

    def test_search_no_results(self, client):
        client.post("/api/v1/cases", json={"title": "Test"})
        resp = client.get("/api/v1/search?q=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_cases"] == 0

    def test_search_by_district(self, client, sample_fir_payload):
        client.post("/api/v1/cases", json=sample_fir_payload)
        resp = client.get("/api/v1/search?q=Mumbai")
        data = resp.json()
        assert data["total_cases"] >= 1

    def test_search_requires_query(self, client):
        resp = client.get("/api/v1/search")
        assert resp.status_code == 422


# ════════════════════════════════════════════════════════════
# Health
# ════════════════════════════════════════════════════════════


class TestHealth:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "healthy"
    def test_nlp_entity_shape_regression(self):
        from app.schemas.entity import ExtractedEntity
        
        # Test the exact production NLP shape
        raw_entity = {
            "id": None,
            "entity_type": "PERSON",
            "value": "Rajesh Kumar",
            "confidence": 0.85,
            "start_offset": 0,
            "end_offset": 12,
            "source_field": "text",
            "case_id": None,
            "confirmed": None
        }
        
        # Ensure it can be parsed by ExtractedEntity without errors
        entity = ExtractedEntity(**raw_entity)
        assert entity.entity_type == "PERSON"
        assert entity.value == "Rajesh Kumar"
        assert entity.confidence == 0.85
