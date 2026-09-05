"""Verify every required Neo4j label and relationship through public Case APIs."""

import json
import os
from uuid import uuid4

import httpx
from sqlalchemy.engine import make_url


def main() -> None:
    database_name = make_url(os.environ["DATABASE_URL"]).database or ""
    if os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic" or not database_name.endswith("_verify"):
        raise RuntimeError("Use only the isolated synthetic verification database")
    base_url = os.environ.get("FIR_SMOKE_API_URL", "http://127.0.0.1:8000")
    suffix = uuid4().hex[:10]
    with httpx.Client(base_url=base_url, timeout=60) as client:
        login = client.post("/api/v1/auth/login", json={
            "email": os.environ["FIR_SMOKE_EMAIL"],
            "password": os.environ["FIR_SMOKE_PASSWORD"],
        })
        login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['access_token']}"

        case_response = client.post("/api/v1/cases", json={
            "case_number": f"GRAPH-DOMAIN-{suffix}",
            "title": f"Synthetic graph domain verification {suffix}",
            "description": "Synthetic-only validation of explicit, officer-reviewed graph assertions.",
            "tags": ["synthetic-verification", "graph-domain"],
        })
        case_response.raise_for_status()
        case_id = case_response.json()["id"]

        values = {
            "PERSON": f"Synthetic Officer Subject {suffix}",
            "PHONE_NUMBER": f"8000{suffix[:6]}",
            "VEHICLE": f"KA 01 ZZ {suffix[:4].upper()}",
            "LOCATION": f"Synthetic District {suffix}",
            "BANK": f"Synthetic Cooperative Bank {suffix}",
            "UPI_ID": f"synthetic.{suffix}@upi",
        }
        entities = {}
        for entity_type, value in values.items():
            response = client.post(f"/api/v1/cases/{case_id}/entities", json={
                "name": value,
                "entity_type": entity_type,
                "description": "Synthetic verification entity; not an allegation.",
                "confidence_score": 1.0,
                "properties": {"verification_scope": "isolated-synthetic"},
            })
            response.raise_for_status()
            entities[entity_type] = response.json()["id"]

        relationships = [
            ("PERSON", "PHONE_NUMBER", "OWNS"),
            ("PERSON", "VEHICLE", "OWNS"),
            ("PERSON", "UPI_ID", "OWNS"),
            ("PERSON", "BANK", "OWNS"),
            ("PERSON", "LOCATION", "LOCATED_AT"),
        ]
        for source_type, target_type, relationship_type in relationships:
            response = client.post(f"/api/v1/cases/{case_id}/relationships", json={
                "source_entity_id": entities[source_type],
                "target_entity_id": entities[target_type],
                "relationship_type": relationship_type,
                "description": "Explicit synthetic assertion created for schema verification.",
                "confidence_score": 1.0,
                "properties": {"reviewed": True, "verification_scope": "isolated-synthetic"},
            })
            response.raise_for_status()

    neo4j_url = os.environ["FIR_SMOKE_NEO4J_HTTP_URL"].rstrip("/")
    response = httpx.post(
        f"{neo4j_url}/db/neo4j/tx/commit",
        auth=("neo4j", os.environ["FIR_SMOKE_NEO4J_PASSWORD"]),
        json={"statements": [
            {
                "statement": (
                    "MATCH (e:Entity)-[:INVOLVED_IN]->(c:Case:CASE {case_id:$case}) "
                    "WITH e,c UNWIND labels(e) AS label "
                    "RETURN collect(DISTINCT label) AS labels, labels(c) AS case_labels, "
                    "count(DISTINCT e) AS memberships"
                ),
                "parameters": {"case": case_id},
            },
            {
                "statement": (
                    "MATCH ()-[r]->() WHERE r.source_case_id=$case "
                    "RETURN collect(DISTINCT type(r)) AS types"
                ),
                "parameters": {"case": case_id},
            },
            {
                "statement": (
                    "MATCH ()-[r]->() WHERE type(r) IN ['CALLED','TRANSFERRED_TO'] "
                    "RETURN collect(DISTINCT type(r)) AS types"
                ),
            },
        ]},
        timeout=30,
    )
    response.raise_for_status()
    graph = response.json()
    if graph["errors"]:
        raise AssertionError(graph["errors"])
    labels = set(graph["results"][0]["data"][0]["row"][0])
    case_labels = set(graph["results"][0]["data"][0]["row"][1])
    memberships = graph["results"][0]["data"][0]["row"][2]
    explicit_types = set(graph["results"][1]["data"][0]["row"][0])
    structured_types = set(graph["results"][2]["data"][0]["row"][0])
    required_labels = {"PERSON", "PHONE", "VEHICLE", "LOCATION", "BANK", "UPI"}
    assert required_labels.issubset(labels), (required_labels, labels)
    assert "CASE" in case_labels and memberships >= len(required_labels)
    assert {"OWNS", "LOCATED_AT"}.issubset(explicit_types), explicit_types
    assert structured_types == {"CALLED", "TRANSFERRED_TO"}, structured_types
    print(json.dumps({
        "status": "passed",
        "case_id": case_id,
        "node_labels": sorted(required_labels | {"CASE"}),
        "relationship_types": ["CALLED", "INVOLVED_IN", "LOCATED_AT", "OWNS", "TRANSFERRED_TO"],
    }))


if __name__ == "__main__":
    main()
