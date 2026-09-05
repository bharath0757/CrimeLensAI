from unittest.mock import patch

import pytest
from app.services.graph_service import GraphService
from fastapi.testclient import TestClient

from app.api import batches
from app.main import app

TOKEN = "isolated-graph-batch-test-service-token-26189"


@pytest.fixture
def client(monkeypatch, store):
    monkeypatch.setenv("SERVICE_AUTH_TOKEN", TOKEN)
    monkeypatch.setattr(batches, "graph_service", GraphService(store))
    return TestClient(app, raise_server_exceptions=False)


def entity(identifier, value):
    return {"kind": "entity", "payload": {"case_id": "case-batch", "entity_id": identifier,
            "entity_type": "PHONE", "value": value, "source_field": "doc-1:row:2:caller"}}


def payload():
    return {"operations": [entity("p1", "9000990189"), entity("p2", "9000990190"),
            {"kind": "relationship", "payload": {"source_entity_id": "p1", "target_entity_id": "p2",
             "relationship_type": "CALLED", "source_case_id": "case-batch", "confidence": 1,
             "why_linked": "Synthetic call reference", "evidence_record_id": "CDR-1"}}]}


def test_credentials_required_before_graph_write(client, monkeypatch):
    assert client.post("/api/v1/batches", json=payload()).status_code == 401
    assert client.post("/api/v1/batches", json=payload(), headers={"X-Service-Token": "wrong"}).status_code == 401
    monkeypatch.delenv("SERVICE_AUTH_TOKEN")
    assert client.post("/api/v1/batches", json=payload()).status_code == 503


def test_complete_batch_and_lost_ack_retry_are_idempotent(client, store):
    for _ in range(2):
        response = client.post("/api/v1/batches", json=payload(), headers={"X-Service-Token": TOKEN})
        assert response.status_code == 200
        assert response.json() == {"processed": 3}
    assert len(store.entities) == 2
    assert len(store.relationships) == 1


def test_partial_failure_never_acknowledges_whole_chunk(client, store):
    with patch.object(batches.graph_service, "create_relationship", side_effect=RuntimeError("Database unavailable")):
        response = client.post("/api/v1/batches", json=payload(), headers={"X-Service-Token": TOKEN})
    assert response.status_code == 500
    assert len(store.entities) == 2
    assert len(store.relationships) == 0
    assert client.post("/api/v1/batches", json=payload(), headers={"X-Service-Token": TOKEN}).json() == {"processed": 3}
    assert len(store.relationships) == 1


def test_invalid_or_oversized_batch_rejected_before_any_write(client, store):
    headers = {"X-Service-Token": TOKEN}
    assert client.post("/api/v1/batches", json={"operations": []}, headers=headers).status_code == 422
    assert client.post("/api/v1/batches", json={"operations": [entity("p1", "9000990189")] * 101}, headers=headers).status_code == 422
    invalid = payload()
    invalid["operations"][-1]["payload"]["relationship_type"] = "INVALID"
    assert client.post("/api/v1/batches", json=invalid, headers=headers).status_code == 422
    assert not store.entities


def test_transfer_metadata_survives_retries_and_preserves_all_sources(client, store):
    value = payload()
    edge = value["operations"][-1]["payload"]
    edge["relationship_type"] = "TRANSFERRED_TO"
    edge["evidence"] = {"timestamp": "2026-09-04T12:00:00Z", "amount": "123.45", "currency": "INR",
                        "sources": [{"document_id": "doc-1", "row_number": 2, "source_sha256": "a" * 64}]}
    headers = {"X-Service-Token": TOKEN}
    assert client.post("/api/v1/batches", json=value, headers=headers).status_code == 200
    edge["evidence"]["sources"] = [{"document_id": "doc-2", "row_number": 3, "source_sha256": "b" * 64}]
    for _ in range(2):
        assert client.post("/api/v1/batches", json=value, headers=headers).status_code == 200
    saved = next(iter(store.relationships.values()))["evidence"]
    assert saved["amount"] == "123.45"
    assert len(saved["sources"]) == 2
    edge["evidence"]["amount"] = "999.99"
    assert client.post("/api/v1/batches", json=value, headers=headers).status_code == 409
    assert next(iter(store.relationships.values()))["evidence"] == saved
