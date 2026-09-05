import asyncio
import os
from decimal import Decimal

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.services.ingestion_delivery import IngestionDelivery
from app.services.structured_ingestion import StructuredIngestion

TEST_URL = os.getenv("CASE_API_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Requires isolated PostgreSQL")


@pytest.fixture
def ingestion_db(database, monkeypatch):
    with database.begin() as connection:
        connection.execute(text("INSERT INTO cases(id,case_number,title,description,owner_id) VALUES ('case-1','case-1','Ingestion test','Synthetic only','test-admin'),('case-2','case-2','Other test','Synthetic only','test-admin')"))
    monkeypatch.setattr(settings, "DATA_BACKEND", "postgres")
    return database


def validated(amount="123.45", identifier="TX-1"):
    return {"input_rows": 1, "records": [{"record_id": identifier, "row_number": 2, "source": "510000000001", "target": "510000000002", "source_type": "BANK_ACCOUNT", "target_type": "BANK_ACCOUNT", "timestamp": "2026-09-04T12:00:00Z", "amount": amount, "upi": "demo.01@upi"}]}


def test_atomic_storage_and_identical_file_retry(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    first = asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), "raw source", "transfers.csv"))
    second = asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), "raw source", "renamed.csv"))
    assert first.id == second.id
    assert first.status == "PENDING"
    with ingestion_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM transactions")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM entities")).scalar_one() == 3
        assert connection.execute(text("SELECT relationship_type FROM relationships")).scalar_one() == "TRANSFERRED_TO"
        assert connection.execute(text("SELECT sum(amount) FROM transactions")).scalar_one() == Decimal("123.45")
        event = connection.execute(text("SELECT event FROM audit_outbox WHERE event->>'record_id'=:id"), {"id": first.id}).scalar_one()
        assert event["resource_type"] == "INGESTION_BATCH"
        assert event["action"] == "INGESTION_BATCH_INSERT"


def test_overlapping_upload_preserves_every_source_reference(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    for index in (1, 2):
        asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(identifier=f"TX-{index}"), f"source-{index}", "source.csv"))
    with ingestion_db.connect() as connection:
        occurrences = connection.execute(text("SELECT properties->'occurrences' FROM entities WHERE name='510000000001'")).scalar_one()
        assert len(occurrences) == 2
        assert len({item["document_id"] for item in occurrences}) == 2
        assert connection.execute(text("SELECT count(*) FROM relationships")).scalar_one() == 2


def test_conflicting_evidence_rolls_back_entire_upload(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), "first source", "first.csv"))
    conflict = validated("999.99")
    conflict["records"].insert(0, validated(identifier="TX-NEW")["records"][0])
    conflict["input_rows"] = 2
    with pytest.raises(HTTPException) as failure:
        asyncio.run(service.ingest("case-1", "test-admin", "transactions", conflict, "conflicting source", "conflict.csv"))
    assert failure.value.status_code == 409
    with ingestion_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM transactions")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM documents")).scalar_one() == 1
        assert connection.execute(text("SELECT count(*) FROM ingestion_batches")).scalar_one() == 1


def test_shared_transaction_id_can_belong_to_two_cases(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    for case_id in ("case-1", "case-2"):
        asyncio.run(service.ingest(case_id, "test-admin", "transactions", validated(), "same source", "source.csv"))
    with ingestion_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM transactions WHERE transaction_id='TX-1'")).scalar_one() == 2


def test_repeated_evidence_retains_relationship_sources_without_double_counting(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    for source in ("source-1", "source-2"):
        asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), source, "source.json"))
    with ingestion_db.connect() as connection:
        refs = connection.execute(text("SELECT properties->'occurrences' FROM relationships")).scalar_one()
        assert len(refs) == 2
        assert len({item["document_id"] for item in refs}) == 2
        assert connection.execute(text("SELECT sum(amount) FROM transactions")).scalar_one() == Decimal("123.45")
        documents = connection.execute(text("SELECT file_type,extracted_entity_count,extracted_relationship_count FROM documents")).all()
        assert all(tuple(item) == ("json", 3, 1) for item in documents)


def test_common_entity_is_captured_once_per_file_with_every_occurrence(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    payload = {"input_rows": 200, "records": [validated(identifier=f"TX-{index}")["records"][0] | {"row_number": index + 2} for index in range(200)]}
    asyncio.run(service.ingest("case-1", "test-admin", "transactions", payload, "large synthetic source", "source.csv"))
    with ingestion_db.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM audit_outbox WHERE event->>'resource_type'='ENTITY'")).scalar_one() == 3
        counts = connection.execute(text("SELECT jsonb_array_length(properties->'occurrences') FROM entities")).scalars().all()
        assert counts == [200, 200, 200]


def test_expired_delivery_claim_replays_same_chunk_and_stale_worker_cannot_finish(ingestion_db):
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    batch = asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), "source", "source.csv"))
    worker = IngestionDelivery(engine_factory=lambda: ingestion_db)
    old = worker._claim()
    assert worker._claim() is None
    with ingestion_db.begin() as connection:
        connection.execute(text("UPDATE ingestion_batches SET claimed_until=NOW()-INTERVAL '1 second'"))
    recovered = worker._claim()
    assert recovered["id"] == old["id"]
    assert recovered["graph_operations"] == old["graph_operations"]
    assert recovered["claim_token"] != old["claim_token"]
    worker._advance(old, len(old["graph_operations"]))
    assert asyncio.run(service.get("case-1", batch.id)).status == "PENDING"
    worker._advance(recovered, len(recovered["graph_operations"]))
    assert asyncio.run(service.get("case-1", batch.id)).status == "COMPLETED"


def test_graph_failure_then_new_worker_recovers_durable_batch(ingestion_db, monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_AUTH_TOKEN", "isolated-service-token-for-ingestion-tests")
    service = StructuredIngestion(engine_factory=lambda: ingestion_db)
    batch = asyncio.run(service.ingest("case-1", "test-admin", "transactions", validated(), "source", "source.csv"))
    failed = IngestionDelivery(engine_factory=lambda: ingestion_db, transport=httpx.MockTransport(lambda request: httpx.Response(503)))
    assert asyncio.run(failed.deliver_one())
    assert asyncio.run(service.get("case-1", batch.id)).status == "PENDING"
    with ingestion_db.begin() as connection:
        connection.execute(text("UPDATE ingestion_batches SET next_attempt_at=NOW()"))
    delivered = []
    def accept(request):
        import json
        assert request.headers["X-Service-Token"] == settings.SERVICE_AUTH_TOKEN
        operations = json.loads(request.content)["operations"]
        delivered.extend(operations)
        return httpx.Response(200, json={"processed": len(operations)})
    resumed = IngestionDelivery(engine_factory=lambda: ingestion_db, transport=httpx.MockTransport(accept))
    assert asyncio.run(resumed.deliver_one())
    assert asyncio.run(service.get("case-1", batch.id)).status == "COMPLETED"
    assert [item["kind"] for item in delivered] == ["entity", "entity", "entity", "relationship"]
    with ingestion_db.connect() as connection:
        assert connection.execute(text("SELECT processing_status FROM documents")).scalar_one() == "COMPLETED"
