"""Real-service FIR gate. Run only against the isolated synthetic verification DB.

Exercises login, file preview/upload, extraction, Postgres storage, direct Neo4j
membership, cross-case linkage, dashboard and automatic audit verification.
Retains the generated synthetic cases so the browser can inspect the same result.
PDF export and production deployment are separate gates, not claimed by this test.
"""

import json
import os
import time
import uuid

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
        raise RuntimeError("This test only writes to the explicitly named isolated verification database")
    base = os.environ.get("FIR_SMOKE_API_URL", "http://127.0.0.1:8000")
    graph_url = os.environ["GRAPH_SERVICE_URL"]
    neo4j_url = os.environ["FIR_SMOKE_NEO4J_HTTP_URL"]
    email, password = os.environ["FIR_SMOKE_EMAIL"], os.environ["FIR_SMOKE_PASSWORD"]
    suffix = uuid.uuid4().hex[:10]
    # Intentionally unfamiliar wording and distinct names, with a repeated identifier.
    narratives = [
        "Synthetic test only. Complainant Kavita Rao received a payment request from "
        "phone 9000990189 in Lucknow. The caller gave UPI demo26189@upi. "
        "This account is an allegation, not an established finding.",
        "Synthetic test only. Witness Manoj Sethi described an unrelated marketplace "
        "complaint in Lucknow. The contact number was +91 90009 90189 and the payment "
        "handle was demo26189@upi. Please verify the source before investigating.",
    ]
    case_ids = []
    masked_case_ids = set()
    with httpx.Client(base_url=base, timeout=120) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        health = call("GET", "/api/v1/health")
        assert health["data_backend"] == "postgres"
        auth = call("POST", "/api/v1/auth/login", json={"email": email, "password": password})
        client.headers["Authorization"] = f"Bearer {auth['access_token']}"
        for index, narrative in enumerate(narratives):
            filename = f"synthetic-unfamiliar-{index}.txt"
            preview = call("POST", "/api/v1/extraction/preview-file", files={"file": (filename, narrative.encode())})
            assert preview["text"] == narrative
            assert any(mention["entity_type"] == "PHONE" for mention in preview["entities"])
            assert preview["model"] != "test-contract"
            case = call("POST", "/api/v1/cases", json={
                "title": f"Synthetic FIR workflow {suffix}-{index}", "description": narrative,
                "case_number": f"SMOKE-{suffix}-{index}", "tags": ["synthetic-verification"],
            })
            case_ids.append(case["id"])
            document = call("POST", f"/api/v1/cases/{case['id']}/documents", files={"file": (filename, narrative.encode())})
            processed = call("POST", f"/api/v1/documents/{document['id']}/process")
            assert processed["success"]
            stored = call("GET", f"/api/v1/documents/{document['id']}")
            assert stored["processing_status"] == "COMPLETED"
            entities = call("GET", f"/api/v1/cases/{case['id']}/entities")
            for entity in entities["items"]:
                reviewed = entity
                if entity.get("is_masked"):
                    masked_case_ids.add(case["id"])
                    assert entity["name"] == "[VICTIM DATA MASKED]"
                    assert all(
                        occurrence["value"] == "[VICTIM DATA MASKED]"
                        for occurrence in entity["properties"]["occurrences"]
                    )
                    reviewed = call(
                        "POST",
                        f"/api/v1/entities/{entity['id']}/unmask",
                        json={"reason": "Verify source provenance for the isolated production workflow"},
                    )
                for occurrence in reviewed["properties"]["occurrences"]:
                    assert narrative[occurrence["start_offset"]:occurrence["end_offset"]] == occurrence["value"]
            assert any(entity["entity_type"] == "PHONE_NUMBER" for entity in entities["items"])

        linked = call("GET", f"/api/v1/cases/{case_ids[0]}/linkage")
        match = next(item for item in linked["linked_cases"] if item["case_id"] == case_ids[1])
        assert match["explanation"] and match["link_strength"] > 0
        assert any(item["entity_type"] == "PHONE" for item in match["shared_entities"])
        assert set(match["score_components"]) == {
            "entity_overlap", "phone_overlap", "transaction_overlap", "location_overlap", "semantic_similarity",
        }
        assert all(value > 0 for value in match["score_components"].values())
        dashboard = call("GET", "/api/v1/dashboard/stats")
        assert dashboard["total_cases"] >= 2

        with httpx.Client(timeout=30) as internal:
            graph_health = internal.get(f"{graph_url}/health").json()
            assert graph_health["neo4j"] == "connected"
            internal.headers["X-Service-Token"] = os.environ["SERVICE_AUTH_TOKEN"]
            alerts = internal.get(f"{graph_url}/api/v1/alerts", params={"case_id": case_ids[0]}).json()["alerts"]
            assert any(set(case_ids).issubset(alert["case_ids"]) for alert in alerts)
            response = internal.post(f"{neo4j_url}/db/neo4j/tx/commit", auth=("neo4j", os.environ["FIR_SMOKE_NEO4J_PASSWORD"]), json={
                "statements": [
                    {"statement": "MATCH (e:Entity:PHONE)-[:INVOLVED_IN]->(c:CASE) WHERE c.case_id IN $cases RETURN e.canonical_value, collect(DISTINCT c.case_id)", "parameters": {"cases": case_ids}},
                    {"statement": "MATCH (e:UPI)-[o:INVOLVED_IN]->(c:CASE) WHERE c.case_id IN $cases RETURN o.source_field, o.start_offset, o.end_offset, o.observed_value", "parameters": {"cases": case_ids}},
                ],
            })
            response.raise_for_status()
            graph_data = response.json()
            assert not graph_data["errors"], graph_data["errors"]
            assert any(row["row"][0] == "9000990189" and set(row["row"][1]) == set(case_ids) for row in graph_data["results"][0]["data"])
            occurrences = graph_data["results"][1]["data"]
            assert len(occurrences) == 2
            for item in occurrences:
                source_field, start, end, value = item["row"]
                assert source_field and isinstance(start, int) and end > start and value == "demo26189@upi"

        engine = create_engine(database_url)
        try:
            with engine.connect() as connection:
                for case_id in case_ids:
                    assert connection.execute(text("SELECT count(*) FROM documents WHERE case_id=:id AND processing_status='COMPLETED'"), {"id": case_id}).scalar_one() == 1
            deadline = time.monotonic() + 30
            while True:
                with engine.connect() as connection:
                    pending = sum(connection.execute(text("SELECT count(*) FROM audit_outbox WHERE event->>'case_id'=:id AND delivered_at IS NULL"), {"id": case_id}).scalar_one() for case_id in case_ids)
                if pending == 0:
                    break
                if time.monotonic() >= deadline:
                    raise AssertionError("Automatic audit delivery did not drain within 30 seconds")
                time.sleep(.25)
        finally:
            engine.dispose()
        for case_id in case_ids:
            chain = call("GET", "/api/v1/ledger/chain", params={"case_id": case_id, "limit": 200})
            actions = {entry["action"] for entry in chain["items"]}
            assert {"CASE_INSERT", "DOCUMENT_INSERT", "ENTITY_INSERT"}.issubset(actions)
            if case_id in masked_case_ids:
                assert "VICTIM_PII_UNMASKED" in actions
            assert all(entry["actor"] == auth["user"]["id"] for entry in chain["items"])
            verification = call("GET", f"/api/v1/ledger/verify/{chain['items'][0]['id']}", params={"case_id": case_id})
            assert verification["verified"]
    print(json.dumps({"case_ids": case_ids, "real_extraction": True, "victim_masking_and_audited_unmask": True, "postgres_verified": True, "neo4j_shared_phone_verified": True, "five_signal_case_linkage": True, "officer_alert_created": True, "audit_verified": True, "retained_synthetic_cases": True}))


if __name__ == "__main__":
    main()
