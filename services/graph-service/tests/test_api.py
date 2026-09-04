import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create a test client with in-memory backend."""
    import os
    os.environ["GRAPH_BACKEND"] = "memory"
    # Clear settings cache so it picks up the env var
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.main import app
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "graph"
        assert "status" in data
    
    def test_health_contains_backend_info(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "backend" in data or "neo4j" in data


class TestEntityEndpoint:
    def test_create_entity(self, client):
        resp = client.post("/api/v1/entities", json={
            "case_id": "CASE-001",
            "entity_type": "PERSON",
            "value": "Rajesh Kumar",
            "confidence": 0.85,
        })
        assert resp.status_code == 200
    
    def test_reject_empty_case_id(self, client):
        resp = client.post("/api/v1/entities", json={
            "case_id": "",
            "entity_type": "PERSON",
            "value": "X",
        })
        assert resp.status_code == 422
    
    def test_reject_invalid_entity_type(self, client):
        resp = client.post("/api/v1/entities", json={
            "case_id": "CASE-001",
            "entity_type": "INVALID",
            "value": "X",
        })
        assert resp.status_code == 422
    
    def test_reject_confidence_out_of_range(self, client):
        resp = client.post("/api/v1/entities", json={
            "case_id": "CASE-001",
            "entity_type": "PERSON",
            "value": "X",
            "confidence": 1.5,
        })
        assert resp.status_code == 422


class TestRelationshipEndpoint:
    def test_reject_invalid_relationship_type(self, client):
        resp = client.post("/api/v1/relationships", json={
            "source_entity_id": "a",
            "target_entity_id": "b",
            "relationship_type": "INVALID_REL_TYPE",
            "source_case_id": "CASE-001",
            "confidence": 0.9,
            "why_linked": "test",
        })
        assert resp.status_code == 422
    
    def test_reject_missing_entities(self, client):
        resp = client.post("/api/v1/relationships", json={
            "source_entity_id": "nonexistent_a",
            "target_entity_id": "nonexistent_b",
            "relationship_type": "USES",
            "source_case_id": "CASE-001",
            "confidence": 0.9,
            "why_linked": "test",
        })
        assert resp.status_code == 404


class TestLinkageEndpoint:
    def test_linkage_empty_case(self, client):
        resp = client.get("/api/v1/linkage/CASE-NONEXISTENT")
        assert resp.status_code == 200


class TestCentralityEndpoint:
    def test_centrality_missing_entity(self, client):
        resp = client.get("/api/v1/centrality/nonexistent")
        assert resp.status_code == 404


class TestCommunitiesEndpoint:
    def test_communities_empty_graph(self, client):
        resp = client.get("/api/v1/communities")
        assert resp.status_code == 200


class TestShortestPathEndpoint:
    def test_shortest_path_missing_entities(self, client):
        resp = client.get("/api/v1/shortest-path", params={
            "entity_a": "nonexistent_a",
            "entity_b": "nonexistent_b",
        })
        assert resp.status_code == 404
    
    def test_shortest_path_missing_params(self, client):
        resp = client.get("/api/v1/shortest-path")
        assert resp.status_code == 422
