"""Opt-in real PostgreSQL verification against an explicitly isolated test database."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DatabaseError

from app.config import Settings
from app.main import create_app
from app.models import AppendRequest
from app.store import LedgerStore, entries

TEST_URL = os.getenv("LEDGER_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Set LEDGER_TEST_POSTGRES_URL to an isolated PostgreSQL database")


@pytest.fixture
def postgres_url():
    url = make_url(TEST_URL)
    # This fixture creates/drops only its own schema in the named test database.
    if url.database != "crimelens_verify":
        pytest.fail("PostgreSQL verification requires the isolated crimelens_verify database")
    schema = "ledger_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    isolated = url.update_query_dict({"options": f"-csearch_path={schema}"})
    try:
        yield isolated.render_as_string(hide_password=False)
    finally:
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


def request():
    return AppendRequest(event_id=uuid4(), record_id="entity-test", case_id="case-test",
                         actor="test-officer", action="ENTITY_CREATED", resource_type="ENTITY", payload={"hash": "synthetic"})


def test_postgres_seed_counts():
    engine = create_engine(TEST_URL)
    try:
        with engine.connect() as connection:
            counts = connection.execute(text(
                "SELECT (SELECT count(*) FROM cases), (SELECT count(*) FROM cdr_records), "
                "(SELECT count(*) FROM transactions)"
            )).one()
            assert tuple(counts) == (1000, 20_000, 20_000)
            assert connection.execute(text("SELECT count(*) FROM relationships WHERE relationship_type='CALLED'")).scalar_one() == 20_000
            assert connection.execute(text("SELECT count(*) FROM relationships WHERE relationship_type='TRANSFERRED_TO'")).scalar_one() == 20_000
    finally:
        engine.dispose()


def test_postgres_parallel_writes_and_retries(postgres_url):
    store = LedgerStore(postgres_url)
    store.initialize()
    shared_event = request()

    def append(index):
        writer = LedgerStore(postgres_url)
        try:
            return writer.append(shared_event if index % 2 == 0 else request())
        finally:
            writer.engine.dispose()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = list(pool.map(append, range(40)))
        assert store.list_records().total == 21
        result = store.verify(records[-1].id)
        assert result.verified and result.checked_through == 21
    finally:
        store.engine.dispose()


@pytest.mark.parametrize("operation", ["UPDATE ledger_entries SET actor='changed'", "DELETE FROM ledger_entries", "TRUNCATE ledger_entries"])
def test_postgres_immutable_trigger(postgres_url, operation):
    store = LedgerStore(postgres_url)
    store.initialize()
    entry = store.append(request())
    try:
        with pytest.raises(DatabaseError), store.engine.begin() as connection:
            connection.execute(text(operation))
        assert store.verify(entry.id).verified
    finally:
        store.engine.dispose()


def test_postgres_privileged_tampering_and_api(postgres_url):
    token = "postgres-verification-service-token-" + "a" * 32
    config = Settings(LEDGER_DATABASE_URL=postgres_url, SERVICE_AUTH_TOKEN=token, ENVIRONMENT="test")
    with TestClient(create_app(config)) as client:
        headers = {"X-Service-Token": token}
        appended = client.post("/api/v1/ledger/record", headers=headers, json=request().model_dump(mode="json"))
        assert appended.status_code == 201
        event_id = appended.json()["record"]["id"]
        assert client.get("/api/v1/ledger/verify/" + event_id, headers=headers).json()["verified"]
        store = client.app.state.store
        with store.engine.begin() as connection:
            connection.execute(text("ALTER TABLE ledger_entries DISABLE TRIGGER ledger_append_only"))
            connection.execute(entries.update().where(entries.c.id == event_id).values(actor="privileged-tamper"))
            connection.execute(text("ALTER TABLE ledger_entries ENABLE TRIGGER ledger_append_only"))
        result = client.get("/api/v1/ledger/verify/" + event_id, headers=headers)
        assert result.status_code == 200 and result.json()["verified"] is False
