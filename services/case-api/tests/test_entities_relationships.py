def test_entity_and_relationship_workflow(client, admin_auth_headers):
    # 1. Create a case
    case_resp = client.post(
        "/api/v1/cases",
        json={"title": "Entity Workflow Case", "description": "Testing entity creation"},
        headers=admin_auth_headers,
    )
    case_id = case_resp.json()["id"]

    # 2. Create entities
    ent1_resp = client.post(
        f"/api/v1/cases/{case_id}/entities",
        json={
            "name": "Suspect X",
            "entity_type": "PERSON",
            "description": "Known smuggler",
        },
        headers=admin_auth_headers,
    )
    assert ent1_resp.status_code == 201
    ent1_id = ent1_resp.json()["id"]

    ent2_resp = client.post(
        f"/api/v1/cases/{case_id}/entities",
        json={
            "name": "Warehouse Alpha",
            "entity_type": "LOCATION",
            "description": "Storage depot",
        },
        headers=admin_auth_headers,
    )
    assert ent2_resp.status_code == 201
    ent2_id = ent2_resp.json()["id"]

    # 3. Create relationship
    rel_resp = client.post(
        f"/api/v1/cases/{case_id}/relationships",
        json={
            "source_entity_id": ent1_id,
            "target_entity_id": ent2_id,
            "relationship_type": "LOCATED_AT",
            "description": "Spotted at location on June 12",
        },
        headers=admin_auth_headers,
    )
    assert rel_resp.status_code == 201
    assert rel_resp.json()["relationship_type"] == "LOCATED_AT"

    # 4. List entities & relationships
    ents_list = client.get(f"/api/v1/cases/{case_id}/entities", headers=admin_auth_headers)
    assert ents_list.status_code == 200
    assert ents_list.json()["total"] >= 2

    rels_list = client.get(f"/api/v1/cases/{case_id}/relationships", headers=admin_auth_headers)
    assert rels_list.status_code == 200
    assert rels_list.json()["total"] >= 1


def test_ai_extraction_ingestion_contract(client, admin_auth_headers):
    # Upload doc to get case & doc id
    case_resp = client.post(
        "/api/v1/cases",
        json={"title": "AI Ingest Case", "description": "Testing AI extraction ingest contract"},
        headers=admin_auth_headers,
    )
    case_id = case_resp.json()["id"]

    doc_resp = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("report.pdf", b"Raw PDF binary content", "application/pdf")},
        headers=admin_auth_headers,
    )
    doc_id = doc_resp.json()["id"]

    # Call AI Extraction Ingestion contract endpoint
    ingest_payload = {
        "document_id": doc_id,
        "case_id": case_id,
        "entities": [
            {
                "name": "Target Alpha",
                "entity_type": "PERSON",
                "confidence_score": 0.96,
            },
            {
                "name": "Cyber Corp",
                "entity_type": "ORGANIZATION",
                "confidence_score": 0.91,
            },
        ],
        "relationships": [
            {
                "source_entity_name": "Target Alpha",
                "target_entity_name": "Cyber Corp",
                "relationship_type": "MEMBER_OF",
                "confidence_score": 0.89,
            }
        ],
    }

    ingest_resp = client.post(
        "/api/v1/integrations/ai/extraction-results",
        json=ingest_payload,
        headers=admin_auth_headers,
    )
    assert ingest_resp.status_code == 200
    data = ingest_resp.json()
    assert data["success"] is True
    assert data["entities_created"] == 2
    assert data["relationships_created"] == 1
