from unittest.mock import AsyncMock

import pytest

from app.api.deps import get_graph_service


def create_case(client, headers, title):
    response = client.post("/api/v1/cases", headers=headers, json={"title": title, "description": "Synthetic linkage authorization test"})
    assert response.status_code == 201
    return response.json()["id"]


def test_linkage_requires_access_to_source_and_every_returned_case(client, admin_auth_headers, investigator_auth_headers):
    from app.main import app

    own = create_case(client, investigator_auth_headers, "Officer assigned case")
    related = create_case(client, investigator_auth_headers, "Accessible related case")
    hidden = create_case(client, admin_auth_headers, "Restricted investigation")
    graph = AsyncMock()
    graph.get_case_linkage.return_value = {"case_id": own, "linked_cases": [
        {"case_id": case_id, "shared_entities": [{"entity_type": "PHONE", "value": phone}], "link_strength": 0.8, "explanation": explanation}
        for case_id, phone, explanation in [(related, "9000990189", "Shared identifier"), (hidden, "9999999999", "Restricted narrative")]
    ]}
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        denied = client.get(f"/api/v1/cases/{hidden}/linkage", headers=investigator_auth_headers)
        assert denied.status_code == 403
        graph.get_case_linkage.assert_not_called()
        response = client.get(f"/api/v1/cases/{own}/linkage", headers=investigator_auth_headers)
        assert response.status_code == 200
        assert [item["case_id"] for item in response.json()["linked_cases"]] == [related]
        assert hidden not in response.text
        assert "Restricted narrative" not in response.text
        assert "9999999999" not in response.text
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_invalid_linkage_response_is_not_shown_as_no_connections(client, admin_auth_headers):
    from app.main import app

    own = create_case(client, admin_auth_headers, "Malformed graph response")
    graph = AsyncMock()
    graph.get_case_linkage.return_value = {"case_id": "wrong-case", "linked_cases": []}
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(f"/api/v1/cases/{own}/linkage", headers=admin_auth_headers)
        assert response.status_code == 502
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_linkage_masks_victim_identifiers_even_for_admin(client, admin_auth_headers):
    from app.main import app

    source = create_case(client, admin_auth_headers, "Victim privacy source")
    related = create_case(client, admin_auth_headers, "Victim privacy related")
    victim_response = client.post(
        f"/api/v1/cases/{source}/entities",
        headers=admin_auth_headers,
        json={
            "name": "Protected Complainant",
            "entity_type": "PERSON",
            "properties": {"privacy_classification": "VICTIM_PII"},
        },
    )
    assert victim_response.status_code == 201
    graph = AsyncMock()
    graph.get_case_linkage.return_value = {
        "case_id": source,
        "linked_cases": [{
            "case_id": related,
            "shared_entities": [{
                "entity_id": "canonical-graph-person-node",
                "entity_type": "PERSON",
                "value": "Protected Complainant",
                "canonical_value": "protected complainant",
            }],
            "link_strength": 0.8,
            "explanation": "Shared protected person record",
        }],
    }
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(f"/api/v1/cases/{source}/linkage", headers=admin_auth_headers)
        assert response.status_code == 200
        assert "Protected Complainant" not in response.text
        shared = response.json()["linked_cases"][0]["shared_entities"][0]
        assert shared["value"] == "[VICTIM DATA MASKED]"
        assert shared["canonical_value"] == "[VICTIM DATA MASKED]"
        assert shared["is_masked"] is True
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_graph_nodes_mask_victim_identifiers(client, admin_auth_headers):
    from app.main import app
    from app.schemas.graph import GraphNode, GraphResponse, GraphStats

    case_id = create_case(client, admin_auth_headers, "Victim graph privacy")
    victim = client.post(
        f"/api/v1/cases/{case_id}/entities",
        headers=admin_auth_headers,
        json={
            "name": "Protected Graph Complainant",
            "entity_type": "PERSON",
            "properties": {
                "privacy_classification": "VICTIM_PII",
                "normalized_value": "protected graph complainant",
            },
        },
    ).json()
    graph = AsyncMock()
    graph.get_case_graph.return_value = GraphResponse(
        case_id=case_id,
        nodes=[GraphNode(
            id=victim["id"],
            label="Protected Graph Complainant",
            type="PERSON",
            properties={"normalized_value": "protected graph complainant"},
        )],
        edges=[],
        stats=GraphStats(total_nodes=1),
    )
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(f"/api/v1/cases/{case_id}/graph", headers=admin_auth_headers)
        assert response.status_code == 200
        assert "Protected Graph Complainant" not in response.text
        node = response.json()["nodes"][0]
        assert node["label"] == "[VICTIM DATA MASKED]"
        assert node["properties"]["normalized_value"] == "[VICTIM DATA MASKED]"
        assert node["properties"]["is_masked"] is True
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


@pytest.mark.parametrize("operation", ["graph", "stats", "connections", "neighbors", "path"])
def test_graph_views_require_case_assignment(client, admin_auth_headers, investigator_auth_headers, operation):
    hidden = create_case(client, admin_auth_headers, "Restricted graph")
    entity = client.post(f"/api/v1/cases/{hidden}/entities", headers=admin_auth_headers,
                         json={"name": "Restricted entity", "entity_type": "PERSON"}).json()["id"]
    paths = {
        "graph": f"/cases/{hidden}/graph",
        "stats": f"/cases/{hidden}/graph/stats",
        "connections": f"/entities/{entity}/connections",
        "neighbors": f"/entities/{entity}/neighbors",
        "path": f"/cases/{hidden}/graph/shortest-path?source_entity_id={entity}&target_entity_id={entity}",
    }
    assert client.get("/api/v1" + paths[operation], headers=investigator_auth_headers).status_code == 403


def test_path_cannot_substitute_entities_from_another_case(client, admin_auth_headers, investigator_auth_headers):
    own = create_case(client, investigator_auth_headers, "Accessible path case")
    hidden = create_case(client, admin_auth_headers, "Other case endpoint")
    entity = client.post(f"/api/v1/cases/{hidden}/entities", headers=admin_auth_headers,
                         json={"name": "Other case person", "entity_type": "PERSON"}).json()["id"]
    response = client.get(f"/api/v1/cases/{own}/graph/shortest-path?source_entity_id={entity}&target_entity_id={entity}", headers=investigator_auth_headers)
    assert response.status_code == 404
