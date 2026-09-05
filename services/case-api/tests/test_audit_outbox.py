"""Real PostgreSQL transactional capture and restart-safe ledger delivery gates."""

import asyncio
import json
import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DatabaseError

from app.core.audit_context import audit_actor, audit_request_id
from app.core.config import settings
from app.integrations.ledger_integration import LedgerService
from app.services.audit_delivery import AuditDelivery

TEST_URL = os.getenv("CASE_API_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Requires isolated PostgreSQL integration database")


def create_case(connection, case_id):
    connection.execute(text("INSERT INTO cases(id,case_number,title,description,owner_id) "
                            "VALUES (:id,:id,'Synthetic audit test','Audit test narrative','test-admin')"), {"id": case_id})


def test_capture_is_atomic_and_attributed(database):
    actor_token = audit_actor.set("verified-officer")
    request_token = audit_request_id.set("server-generated-request")
    try:
        with database.begin() as connection:
            create_case(connection, "case-atomic")
        with pytest.raises(RuntimeError), database.begin() as connection:
            create_case(connection, "case-rollback")
            raise RuntimeError("Force transaction rollback")
    finally:
        audit_actor.reset(actor_token)
        audit_request_id.reset(request_token)
    with database.connect() as connection:
        events = connection.execute(text("SELECT event FROM audit_outbox")).scalars().all()
        assert len(events) == 1
        assert events[0]["actor"] == "verified-officer"
        assert events[0]["record_id"] == "case-atomic"
        assert events[0]["payload"]["request_id"] == "server-generated-request"
        assert "Audit test narrative" not in str(events)
        assert len(events[0]["payload"]["snapshot_hash"]) == 64
        assert connection.execute(text("SELECT count(*) FROM cases WHERE id='case-rollback'")).scalar_one() == 0


def test_all_domain_tables_and_immutable_event_content(database):
    worker = AuditDelivery(engine_factory=lambda: database)
    worker.ensure_ready()
    with database.begin() as connection:
        create_case(connection, "case-all")
        connection.execute(text("UPDATE cases SET title='Changed audit title' WHERE id='case-all'"))
        connection.execute(text("INSERT INTO entities(id,case_id,name,normalized_value,entity_type) "
                                "VALUES ('e1','case-all','Phone 1','1','PHONE_NUMBER'),('e2','case-all','Phone 2','2','PHONE_NUMBER')"))
        connection.execute(text("INSERT INTO relationships(id,case_id,source_entity_id,target_entity_id,relationship_type) "
                                "VALUES ('r1','case-all','e1','e2','CALLED')"))
        connection.execute(text("INSERT INTO documents(id,case_id,filename,original_filename,file_type,file_size_bytes,uploaded_by) "
                                "VALUES ('d1','case-all','fir.txt','fir.txt','txt',5,'officer')"))
        connection.execute(text("INSERT INTO cdr_records VALUES ('cdr1','case-all','1','2',NOW(),30,'tower','imei')"))
        connection.execute(text("INSERT INTO transactions VALUES ('txn1','case-all','bank1','bank2',100,'synthetic@upi',NOW())"))
        connection.execute(text("UPDATE users SET full_name='Updated Test Admin' WHERE id='test-admin'"))
        connection.execute(text("DELETE FROM entities WHERE id='e1'"))
    with database.connect() as connection:
        events = connection.execute(text("SELECT event FROM audit_outbox ORDER BY sequence")).scalars().all()
        assert {event["resource_type"] for event in events} == {"CASE", "ENTITY", "RELATIONSHIP", "DOCUMENT", "CDR", "TRANSACTION", "USER"}
        assert any(event["action"] == "RELATIONSHIP_DELETE" for event in events)  # FK cascade audited
        assert any(event["action"] == "ENTITY_DELETE" for event in events)
    with pytest.raises(DatabaseError), database.begin() as connection:
        connection.execute(text("UPDATE audit_outbox SET event='{}'::jsonb"))
    with pytest.raises(DatabaseError), database.begin() as connection:
        connection.execute(text("DELETE FROM audit_outbox"))


def test_delivery_survives_acknowledgement_loss(database, monkeypatch):
    ledger_url = os.getenv("CASE_API_TEST_LEDGER_URL")
    if not ledger_url:
        pytest.skip("Requires the isolated running ledger HTTP service")
    monkeypatch.setattr(settings, "LEDGER_SERVICE_URL", ledger_url)
    monkeypatch.setattr(settings, "SERVICE_AUTH_TOKEN", os.environ["CASE_API_TEST_LEDGER_TOKEN"])
    case_id = "outbox-" + uuid4().hex
    with database.begin() as connection:
        create_case(connection, case_id)
    actual = LedgerService()

    class LostAcknowledgement:
        async def append(self, event):
            await actual.append(event)
            raise TimeoutError("Response lost after the real ledger committed")

    async def exercise():
        first_worker = AuditDelivery(LostAcknowledgement(), engine_factory=lambda: database)
        assert await first_worker.deliver_one()
        with database.begin() as connection:
            row = connection.execute(text("SELECT event_id,delivered_at,attempts FROM audit_outbox")).one()
            assert row.delivered_at is None and row.attempts == 1
            connection.execute(text("UPDATE audit_outbox SET next_attempt_at=NOW()"))
        # A new worker/process retries the retained event UUID.
        restarted_worker = AuditDelivery(actual, engine_factory=lambda: database)
        assert await restarted_worker.deliver_one()
        with database.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM audit_outbox WHERE delivered_at IS NOT NULL")).scalar_one() == 1
        chain = await actual.chain(50, 0, [case_id])
        assert chain.total == 1
        assert (await actual.verify(chain.records[0].id, [case_id])).verified
    asyncio.run(exercise())


def test_expired_claim_is_recovered(database):
    with database.begin() as connection:
        create_case(connection, "case-lease")
    worker = AuditDelivery(engine_factory=lambda: database)
    claimed = worker._claim()
    assert claimed is not None
    assert AuditDelivery(engine_factory=lambda: database)._claim() is None
    with database.begin() as connection:
        connection.execute(text("UPDATE audit_outbox SET claimed_until=NOW()-INTERVAL '1 second'"))
    recovered = AuditDelivery(engine_factory=lambda: database)._claim()
    assert recovered["event_id"] == claimed["event_id"]
    assert recovered["claim_token"] != claimed["claim_token"]


def test_legacy_malformed_capture_is_preserved_not_rewritten(database):
    from types import SimpleNamespace

    event_id = str(uuid4())
    original = {"event_id": event_id, "record_id": "legacy-batch", "case_id": "case-legacy",
                "actor": "test-admin", "action": None, "resource_type": None,
                "payload": {"snapshot_hash": "a" * 64, "operation": "INSERT"}}
    with database.begin() as connection:
        connection.execute(text("INSERT INTO audit_outbox(event_id,event) VALUES (CAST(:id AS uuid),CAST(:event AS jsonb))"), {"id": event_id, "event": json.dumps(original)})
    received = []

    async def append(event):
        received.append(event)
        return {"record": {"id": event_id, "hash": "b" * 64}}

    worker = AuditDelivery(SimpleNamespace(append=append), engine_factory=lambda: database)
    assert asyncio.run(worker.deliver_one())
    assert received[0]["action"] == "MALFORMED_CAPTURE_PRESERVED"
    assert received[0]["payload"]["original_event"] == original
    with database.connect() as connection:
        saved = connection.execute(text("SELECT event,delivered_at FROM audit_outbox")).one()
        assert saved.event == original
        assert saved.delivered_at is not None


def test_incorrect_ledger_receipt_does_not_mark_delivered(database):
    from types import SimpleNamespace

    with database.begin() as connection:
        create_case(connection, "case-receipt")

    async def append(event):
        return {"record": {"id": str(uuid4()), "hash": "a" * 64}}

    worker = AuditDelivery(SimpleNamespace(append=append), engine_factory=lambda: database)
    assert asyncio.run(worker.deliver_one())
    with database.connect() as connection:
        saved = connection.execute(text("SELECT delivered_at,last_error FROM audit_outbox")).one()
        assert saved.delivered_at is None
        assert saved.last_error.startswith("ValueError")


def test_postgres_entity_normalization_and_occurrence_preservation(database):
    from app.repositories.postgres import PostgresEntityRepository
    from app.schemas.entity import EntityCreate, EntityType, EntityUpdate

    with database.begin() as connection:
        create_case(connection, "case-entities")

    async def exercise():
        repository = PostgresEntityRepository()
        first = await repository.create("case-entities", EntityCreate(
            name="9876543210", entity_type=EntityType.PHONE_NUMBER,
            properties={"occurrences": [{"document_id": "one", "start_offset": 10}]},
        ))
        second = await repository.create("case-entities", EntityCreate(
            name="+91 98765 43210", entity_type=EntityType.PHONE_NUMBER,
            properties={"occurrences": [{"document_id": "two", "start_offset": 20}]},
        ))
        assert first.id == second.id
        assert len(second.properties["occurrences"]) == 2
        await repository.update(first.id, EntityUpdate(name="9123456789"))
        assert await repository.update(first.id, EntityUpdate(name=None))
        variant = await repository.create("case-entities", EntityCreate(name="+91 91234 56789", entity_type=EntityType.PHONE_NUMBER))
        assert variant.id == first.id
        assert await repository.count("case-entities") == 1
    asyncio.run(exercise())


def test_postgres_retains_distinct_transfer_events_and_deduplicates_retries(database):
    from app.core.exceptions import CrimeLensException
    from app.repositories.postgres import (
        PostgresEntityRepository,
        PostgresRelationshipRepository,
    )
    from app.schemas.entity import EntityCreate, EntityType
    from app.schemas.relationship import RelationshipCreate, RelationshipType

    with database.begin() as connection:
        create_case(connection, "case-transfers")

    async def exercise():
        entities, relationships = PostgresEntityRepository(), PostgresRelationshipRepository()
        source = await entities.create("case-transfers", EntityCreate(name="123456789", entity_type=EntityType.BANK_ACCOUNT))
        target = await entities.create("case-transfers", EntityCreate(name="234567891", entity_type=EntityType.BANK_ACCOUNT))
        base = {"source_entity_id": source.id, "target_entity_id": target.id, "relationship_type": RelationshipType.TRANSFERRED_TO}
        event1 = RelationshipCreate(**base, properties={"transaction_id": "txn-one", "amount": 100})
        first = await relationships.create("case-transfers", event1)
        assert (await relationships.create("case-transfers", event1)).id == first.id
        second = await relationships.create("case-transfers", RelationshipCreate(**base, properties={"transaction_id": "txn-two", "amount": 200}))
        assert first.id != second.id
        assert await relationships.count("case-transfers") == 2
        with pytest.raises(CrimeLensException):
            await relationships.create("case-transfers", RelationshipCreate(**base, properties={"transaction_id": "txn-one", "amount": 999}))
    asyncio.run(exercise())


def test_postgres_case_document_and_user_crud(database):
    from app.repositories.postgres import (
        PostgresCaseRepository,
        PostgresDocumentRepository,
        PostgresUserRepository,
    )
    from app.schemas.case import CaseCreate, CaseUpdate
    from app.schemas.document import ProcessingStatus
    from app.schemas.user import UserCreate, UserRole

    async def exercise():
        users, cases, documents = PostgresUserRepository(), PostgresCaseRepository(), PostgresDocumentRepository()
        user = await users.create(UserCreate(email="test-investigator@example.org", full_name="Test Investigator", password="SyntheticTest123!", role=UserRole.INVESTIGATOR))
        assert (await users.get_by_email(user.email)).id == user.id
        case = await cases.create(CaseCreate(title="Database integration", description="Synthetic case metadata"), owner_id=user.id)
        assert (await cases.list_cases(owner_id=user.id))[1] == 1
        await cases.update(case.id, CaseUpdate(title="Updated integration case"))
        document = await documents.create(case.id, "fir.txt", "fir.txt", "txt", 10, "/data/uploads/fir.txt", user.id)
        await cases.update_counts(case.id, doc_delta=1)
        await documents.update_status(document.id, ProcessingStatus.COMPLETED)
        assert (await documents.get_by_id(document.id)).processing_status == ProcessingStatus.COMPLETED
        assert (await cases.get_by_id(case.id)).document_count == 1
        assert await documents.delete(document.id) == "/data/uploads/fir.txt"
        assert await cases.delete(case.id)
        assert await cases.get_by_id(case.id) is None
    asyncio.run(exercise())
