"""Synthetic-only real CSV import gate: gateway, validator, PostgreSQL, Neo4j, ledger."""

import json
import os
import time
from decimal import Decimal
from uuid import uuid4

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    database_url = os.environ["DATABASE_URL"]
    expected_database = os.environ.get("FIR_SMOKE_EXPECTED_DATABASE", "crimelens_verify")
    if (
        os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic"
        or make_url(database_url).database != expected_database
        or not expected_database.endswith("verify")
    ):
        raise RuntimeError("Use only the isolated synthetic verification database")
    engine = create_engine(database_url)
    suffix = uuid4().hex[:10]
    with httpx.Client(base_url="http://127.0.0.1:8000", timeout=60) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()
        login = call("POST", "/api/v1/auth/login", json={"email": os.environ["FIR_SMOKE_EMAIL"], "password": os.environ["FIR_SMOKE_PASSWORD"]})
        client.headers["Authorization"] = f"Bearer {login['access_token']}"
        case = call("POST", "/api/v1/cases", json={"title": f"Synthetic structured import {suffix}", "description": "Synthetic CDR and transaction integration verification", "tags": ["synthetic-verification"]})
        case_id = case["id"]
        cdr = "cdr_id,caller,receiver,timestamp,duration,tower,imei\n" + f"C-{suffix}-1,9000990189,9000990190,2026-09-04T12:00:00Z,45,TWR-TEST-01,860000000000001\nC-{suffix}-2,9000990190,9000990191,2026-09-04T12:01:00Z,30,TWR-TEST-01,860000000000001\n"
        transactions = "transaction_id,sender,receiver,amount,upi,timestamp\n" + f"T-{suffix}-1,510000000001,510000000002,123.45,synthetic.01@upi,2026-09-04T12:00:00Z\nT-{suffix}-2,510000000002,510000000003,76.55,synthetic.02@upi,2026-09-04T12:01:00Z\n"
        batches = []
        for kind, source in (("cdr", cdr), ("transactions", transactions)):
            path = f"/api/v1/cases/{case_id}/ingestion/csv?kind={kind}"
            batch = call("POST", path, files={"file": (kind + ".csv", source.encode(), "text/csv")})
            repeated = call("POST", path, files={"file": ("renamed.csv", source.encode(), "text/csv")})
            assert repeated["id"] == batch["id"]
            assert batch["inserted_records"] == 2
            batches.append(batch)
            original = client.get(f"/api/v1/cases/{case_id}/ingestion/{batch['id']}/source")
            original.raise_for_status()
            assert original.content == source.encode()
        deadline = time.monotonic() + 45
        while True:
            statuses = [call("GET", f"/api/v1/cases/{case_id}/ingestion/{batch['id']}") for batch in batches]
            if all(batch["status"] == "COMPLETED" for batch in statuses):
                break
            assert time.monotonic() < deadline, statuses
            time.sleep(1)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT count(*) FROM cdr_records WHERE case_id=:case"), {"case": case_id}).scalar_one() == 2
            assert connection.execute(text("SELECT sum(amount) FROM transactions WHERE case_id=:case"), {"case": case_id}).scalar_one() == Decimal("200.00")
            assert connection.execute(text("SELECT count(*) FROM documents WHERE case_id=:case AND processing_status='COMPLETED'"), {"case": case_id}).scalar_one() == 2
            assert connection.execute(text("SELECT count(*) FROM entities WHERE case_id=:case AND entity_type='UPI_ID'"), {"case": case_id}).scalar_one() == 2
        neo4j_url = os.environ["FIR_SMOKE_NEO4J_HTTP_URL"]
        response = httpx.post(f"{neo4j_url}/db/neo4j/tx/commit", auth=("neo4j", os.environ["FIR_SMOKE_NEO4J_PASSWORD"]), json={"statements": [{"statement": "MATCH ()-[r]->() WHERE r.source_case_id=$case AND type(r) IN ['CALLED','TRANSFERRED_TO','LOCATED_AT'] RETURN type(r),count(*)", "parameters": {"case": case_id}}]}, timeout=30)
        response.raise_for_status()
        graph = response.json()
        assert not graph["errors"]
        counts = dict(item["row"] for item in graph["results"][0]["data"])
        assert counts == {"CALLED": 2, "TRANSFERRED_TO": 2, "LOCATED_AT": 2}, counts
        response = httpx.post(f"{neo4j_url}/db/neo4j/tx/commit", auth=("neo4j", os.environ["FIR_SMOKE_NEO4J_PASSWORD"]), json={"statements": [{"statement": "MATCH ()-[r:TRANSFERRED_TO]->() WHERE r.source_case_id=$case RETURN sum(r.amount_minor),collect(r.evidence_json)", "parameters": {"case": case_id}}]}, timeout=30)
        response.raise_for_status()
        financial_graph = response.json()
        assert not financial_graph["errors"]
        amount_minor, evidence_rows = financial_graph["results"][0]["data"][0]["row"]
        assert amount_minor == 20_000
        assert all(json.loads(value)["sources"][0]["source_sha256"] for value in evidence_rows)
        deadline = time.monotonic() + 45
        while True:
            with engine.connect() as connection:
                pending = connection.execute(text("SELECT count(*) FROM audit_outbox WHERE event->>'case_id'=:case AND delivered_at IS NULL"), {"case": case_id}).scalar_one()
            if pending == 0:
                break
            assert time.monotonic() < deadline, "Audit delivery did not finish"
            time.sleep(1)
        chain = call("GET", f"/api/v1/ledger/chain?case_id={case_id}&limit=200")
        assert chain["items"]
        assert call("GET", f"/api/v1/ledger/verify/{chain['items'][0]['id']}?case_id={case_id}")["verified"]
        print(json.dumps({"status": "passed", "case_id": case_id, "cdr_records": 2, "transactions": 2, "money": "200.00", "graph": counts, "duplicates_prevented": True, "original_sources_retained": True, "audit_verified": True}))
    engine.dispose()


if __name__ == "__main__":
    main()
