"""Unit integration gates, with explicit substitutes only at service boundaries."""

import asyncio
import json
from unittest.mock import AsyncMock

import httpx
import pytest

from app.core.config import settings
from app.integrations.ai_integration import IntegratedAIService
from app.integrations.graph_integration import IntegratedGraphService
from app.repositories.case_repo import InMemoryCaseRepository
from app.repositories.document_repo import InMemoryDocumentRepository
from app.repositories.entity_repo import InMemoryEntityRepository
from app.schemas.case import CaseCreate
from app.schemas.document import ProcessingStatus
from app.schemas.entity import EntityCreate, EntityType
from app.services.document_text import DocumentTextError, read_document


def test_uploaded_text_is_sent_and_preserved_without_inventing_relationships(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    narrative = "Witness reported phone 9123456789 near a bus stop."
    path = tmp_path / "unfamiliar.txt"
    path.write_text(narrative, encoding="utf-8")
    observed = []

    def extraction(request):
        body = json.loads(request.content)
        observed.append(body)
        offset = body["text"].index("9123456789")
        return httpx.Response(200, json={"model": "test-contract", "entities": [{
            "entity_id": "mention-1", "entity_type": "PHONE", "value": "9123456789",
            "normalized_value": "+919123456789", "confidence": .98,
            "start_offset": offset, "end_offset": offset + 10,
            "source_field": "document_text", "case_id": body["case_id"],
        }]})

    async def exercise():
        cases, docs, entities = InMemoryCaseRepository(), InMemoryDocumentRepository(), InMemoryEntityRepository()
        case = await cases.create(CaseCreate(title="Unfamiliar FIR", description=narrative), owner_id="user-admin-001")
        doc = await docs.create(case.id, path.name, path.name, "txt", path.stat().st_size, str(path), "officer")
        graph = AsyncMock()
        service = IntegratedAIService(docs, entities, cases, graph, transport=httpx.MockTransport(extraction))
        assert await service.process_document(doc.id, case.id, str(path))
        assert await service.process_document(doc.id, case.id, str(path))
        assert len(observed) == 1
        assert observed[0]["text"] == narrative
        items, count = await entities.list_by_case(case.id)
        assert count == 1
        entity = items[0]
        assert entity.entity_type == EntityType.PHONE_NUMBER
        assert entity.name == "9123456789"
        occurrence = entity.properties["occurrences"][0]
        assert occurrence["document_sha256"] == read_document(str(path)).sha256
        assert narrative[occurrence["start_offset"]:occurrence["end_offset"]] == entity.name
        assert graph.sync_entity.await_count == 1
        graph.sync_relationship.assert_not_called()
        status = await service.get_processing_status(doc.id)
        assert status.processing_status == ProcessingStatus.COMPLETED
        assert status.extracted_entity_count == 1
        assert status.extracted_relationship_count == 0
    asyncio.run(exercise())


def test_graph_failure_is_not_reported_as_completed(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path))
    path = tmp_path / "fir.txt"
    path.write_text("9123456789", encoding="utf-8")

    async def exercise():
        cases, docs, entities = InMemoryCaseRepository(), InMemoryDocumentRepository(), InMemoryEntityRepository()
        case = await cases.create(CaseCreate(title="Graph retry", description="Graph synchronization retry regression"), owner_id="user-admin-001")
        doc = await docs.create(case.id, path.name, path.name, "txt", 10, str(path), "officer")
        graph = AsyncMock()
        graph.sync_entity.side_effect = httpx.ConnectError("service offline")
        transport = httpx.MockTransport(lambda _: httpx.Response(200, json={
            "model": "test-contract", "entities": [{
                "entity_id": "mention", "entity_type": "PHONE", "value": "9123456789",
                "normalized_value": "+919123456789", "confidence": .98,
                "start_offset": 0, "end_offset": 10, "source_field": "document_text", "case_id": case.id,
            }],
        }))
        service = IntegratedAIService(docs, entities, cases, graph, transport=transport)
        assert not await service.process_document(doc.id, case.id, str(path))
        assert (await docs.get_by_id(doc.id)).processing_status == ProcessingStatus.FAILED
        graph.sync_entity.side_effect = None
        assert await service.process_document(doc.id, case.id, str(path))
        assert (await entities.list_by_case(case.id))[1] == 1
        assert (await cases.get_by_id(case.id)).entity_count == 1
    asyncio.run(exercise())


def test_invalid_offsets_rejected_before_entity_write():
    transport = httpx.MockTransport(lambda _: httpx.Response(200, json={
        "model": "test-contract", "entities": [{
            "entity_id": "mention", "entity_type": "PHONE", "value": "9123456789",
            "normalized_value": "+919123456789", "confidence": .98,
            "start_offset": 0, "end_offset": 10, "source_field": "document_text", "case_id": None,
        }],
    }))
    with pytest.raises(ValueError, match="invalid source provenance"):
        asyncio.run(IntegratedAIService(transport=transport).extract_text("not a phone number"))


def test_document_reader_rejects_outside_upload_directory(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "UPLOAD_DIR", str(tmp_path / "uploads"))
    outside = tmp_path / "outside.txt"
    outside.write_text("sensitive", encoding="utf-8")
    with pytest.raises(DocumentTextError, match="evidence directory"):
        read_document(str(outside))


def test_phone_variants_share_graph_id_across_cases():
    async def exercise():
        repo = InMemoryEntityRepository()
        first = await repo.create("one", EntityCreate(name="9876543210", entity_type=EntityType.PHONE_NUMBER))
        second = await repo.create("two", EntityCreate(name="+91 98765 43210", entity_type=EntityType.PHONE_NUMBER))
        assert first.id != second.id
        assert IntegratedGraphService._graph_entity_id(first) == IntegratedGraphService._graph_entity_id(second)
    asyncio.run(exercise())


def test_graph_identity_cannot_be_overridden_by_arbitrary_properties():
    async def exercise():
        repository = InMemoryEntityRepository()
        first = await repository.create("one", EntityCreate(
            name="9876543210", entity_type=EntityType.PHONE_NUMBER,
            properties={"normalized_value": "9123456789"},
        ))
        second = await repository.create("two", EntityCreate(name="9876543210", entity_type=EntityType.PHONE_NUMBER))
        assert IntegratedGraphService._graph_entity_id(first) == IntegratedGraphService._graph_entity_id(second)
    asyncio.run(exercise())
