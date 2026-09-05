"""Real file-backed ledger tests; PostgreSQL has a separate deployment gate."""

from concurrent.futures import ThreadPoolExecutor
from itertools import pairwise
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import DatabaseError

from app.config import Settings
from app.main import create_app
from app.models import AppendRequest
from app.store import ChainCorrupted, LedgerStore, entries

TOKEN = "test-service-token-only-" + "a" * 40
AUTH = {"X-Service-Token": TOKEN}


@pytest.fixture
def store(tmp_path):
    instance = LedgerStore(f"sqlite:///{tmp_path / 'ledger.db'}")
    instance.initialize()
    yield instance
    instance.engine.dispose()


@pytest.fixture
def client(tmp_path):
    config = Settings(LEDGER_DATABASE_URL=f"sqlite:///{tmp_path / 'api.db'}", SERVICE_AUTH_TOKEN=TOKEN)
    with TestClient(create_app(config)) as instance:
        yield instance


def event(**overrides):
    return AppendRequest(**{
        "event_id": uuid4(), "record_id": "entity-1", "case_id": "case-1",
        "actor": "officer-1", "action": "ENTITY_CREATED", "resource_type": "ENTITY",
        "payload": {"value": "Synthetic evidence", "confidence": .95}, **overrides,
    })


def test_append_verify_persistence_and_idempotency(store):
    request = event()
    first = store.append(request)
    assert first.sequence == 1 and first.previous_hash == "0" * 64
    assert len(first.hash) == 64
    assert store.append(request) == first
    second = store.append(event(record_id="entity-2"))
    assert second.previous_hash == first.hash
    reopened = LedgerStore(str(store.engine.url))
    reopened.initialize()
    result = reopened.verify(first.id)
    assert result.verified and result.checked_records == 2
    assert result.checkpoint_hash == second.hash
    assert reopened.list_records().total == 2
    reopened.engine.dispose()


def test_atomic_batch_append_and_idempotent_retry(store):
    requests = [event(record_id=f"batch-{index}") for index in range(25)]
    records = store.append_many(requests)
    assert [record.sequence for record in records] == list(range(1, 26))
    assert all(current.previous_hash == previous.hash for previous, current in pairwise(records))
    assert store.append_many(requests) == records
    assert store.list_records().total == 25
    assert store.verify(records[-1].id).verified


def test_concurrent_writers_have_one_chain(store):
    # Independent connections, not a process-local Python mutex.
    def write(index):
        writer = LedgerStore(str(store.engine.url))
        try:
            return writer.append(event(record_id=f"entity-{index}"))
        finally:
            writer.engine.dispose()
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(write, range(40)))
    assert sorted(record.sequence for record in records) == list(range(1, 41))
    assert store.verify(records[0].id).verified


def test_concurrent_retries_are_one_event(store):
    request = event()
    with ThreadPoolExecutor(max_workers=8) as pool:
        records = list(pool.map(lambda _: store.append(request), range(24)))
    assert {record.id for record in records} == {str(request.event_id)}
    assert store.list_records().total == 1


@pytest.mark.parametrize("column,value", [
    ("actor", "attacker"), ("action", "DELETED"), ("record_id", "other-record"),
    ("case_id", "other-case"), ("payload", '{"value":"changed"}'),
    ("previous_hash", "f" * 64), ("timestamp", "2000-01-01T00:00:00+00:00"),
    ("hash", "e" * 64),
])
def test_privileged_tampering_detected(store, column, value):
    first = store.append(event())
    second = store.append(event())
    with store.engine.begin() as connection:
        # Simulate a privileged operator bypassing the append-only trigger.
        connection.exec_driver_sql("DROP TRIGGER ledger_no_update")
        connection.execute(entries.update().where(entries.c.id == first.id).values(**{column: value}))
    result = store.verify(second.id)
    assert not result.verified
    assert result.error_sequence == 1


def test_append_only_trigger_rejects_update_and_delete(store):
    record = store.append(event())
    with pytest.raises(DatabaseError), store.engine.begin() as connection:
        connection.execute(entries.update().where(entries.c.id == record.id).values(actor="changed"))
    with pytest.raises(DatabaseError), store.engine.begin() as connection:
        connection.execute(entries.delete().where(entries.c.id == record.id))


def test_tail_deletion_detected_and_new_append_refused(store):
    first = store.append(event())
    tail = store.append(event())
    with store.engine.begin() as connection:
        connection.exec_driver_sql("DROP TRIGGER ledger_no_delete")
        connection.execute(entries.delete().where(entries.c.id == tail.id))
    assert not store.verify(first.id).verified
    with pytest.raises(ChainCorrupted):
        store.append(event())


def test_auth_unknown_record_and_conflicting_retry(client):
    body = event().model_dump(mode="json")
    assert client.post("/api/v1/ledger/record", json=body).status_code == 401
    assert client.get("/api/v1/ledger/chain").status_code == 401
    created = client.post("/api/v1/ledger/record", json=body, headers=AUTH)
    assert created.status_code == 201
    body["actor"] = "another-officer"
    assert client.post("/api/v1/ledger/record", json=body, headers=AUTH).status_code == 409
    assert client.get("/api/v1/ledger/verify/unknown", headers=AUTH).status_code == 404
    assert client.get("/api/v1/ledger/verify/" + created.json()["record"]["id"], headers=AUTH).json()["verified"]


def test_authenticated_batch_endpoint(client):
    bodies = [event(record_id=f"api-batch-{index}").model_dump(mode="json") for index in range(3)]
    assert client.post("/api/v1/ledger/batch", json={"events": bodies}).status_code == 401
    response = client.post("/api/v1/ledger/batch", json={"events": bodies}, headers=AUTH)
    assert response.status_code == 201
    records = response.json()["records"]
    assert [record["sequence"] for record in records] == [1, 2, 3]
    assert client.post(
        "/api/v1/ledger/batch", json={"events": [bodies[0], bodies[0]]}, headers=AUTH
    ).status_code == 422


def test_case_filter_and_pagination(store):
    one = store.append(event(case_id="one"))
    store.append(event(case_id="two"))
    store.append(event(case_id="two"))
    assert store.list_records(case_ids=["two"], limit=1, offset=1).total == 2
    assert store.list_records(case_ids=[]).total == 0
    with pytest.raises(KeyError):
        store.verify(one.id, case_ids=["two"])


def test_canonical_object_keys_retry_and_unicode(store):
    request = event(payload={"z": "తెలుగు", "a": {"2": 2, "1": 1}})
    first = store.append(request)
    retry = request.model_copy(update={"payload": {"a": {"1": 1, "2": 2}, "z": "తెలుగు"}})
    assert store.append(retry).hash == first.hash


def test_health_and_masking(client):
    assert client.get("/api/v1/health").json()["status"] == "healthy"
    response = client.post("/api/v1/privacy/mask", headers=AUTH, json={
        "data": {"victim_name": "Synthetic Person", "nested": [{"aadhaar": "234567890123"}], "case_id": "one"},
    })
    assert response.json()["masked_data"] == {
        "victim_name": "[REDACTED]", "nested": [{"aadhaar": "[REDACTED]"}], "case_id": "one",
    }


def test_fail_closed_configuration():
    with pytest.raises(ValueError, match="SERVICE_AUTH_TOKEN"):
        Settings().validate_runtime()
    with pytest.raises(ValueError, match="PostgreSQL"):
        Settings(SERVICE_AUTH_TOKEN=TOKEN, LEDGER_DATABASE_URL="sqlite:///test.db", ENVIRONMENT="production").validate_runtime()


def test_openapi_has_typed_responses(client):
    document = client.get("/api/v1/openapi.json").json()
    for route in ("/api/v1/ledger/chain", "/api/v1/ledger/verify/{record_id}"):
        assert "$ref" in document["paths"][route]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert document["paths"]["/api/v1/ledger/record"]["post"]["security"]


def test_empty_field_override_cannot_unmask_victim(client):
    response = client.post("/api/v1/privacy/mask", headers=AUTH, json={
        "data": {"victim_name": "Synthetic Person"}, "sensitive_fields": [],
    })
    assert response.json()["masked_data"]["victim_name"] == "[REDACTED]"
