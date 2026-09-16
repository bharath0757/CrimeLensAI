import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, call

from app.api.deps import get_graph_service
from app.integrations.graph_integration import IntegratedGraphService
from app.schemas.graph import CentralityMetrics, CentralityResponse


def _case(client, headers, title):
    response = client.post(
        "/api/v1/cases", headers=headers,
        json={"title": title, "description": "Case insights test"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_graph_integration_proxies_analytics_and_translates_entity_ids():
    entity = SimpleNamespace(
        id="local-person-id", name="Observed Contact",
        entity_type=SimpleNamespace(value="PERSON"),
    )
    entity_repo = AsyncMock()
    entity_repo.list_by_case.return_value = ([entity], 1)
    entity_repo.get_by_id.return_value = entity
    service = IntegratedGraphService(ent_repo=entity_repo, rel_repo=AsyncMock())
    graph_id = service._graph_entity_id(entity)
    service._request = AsyncMock(side_effect=[
        {
            "case_id": "case-1",
            "patterns": [{
                "pattern_type": "BRIDGE_ENTITY", "case_ids": ["case-1"],
                "confidence": 0.75, "supporting_entity_ids": [graph_id],
                "explanation": "upstream", "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            }],
        },
        {
            "entity_id": graph_id,
            "centrality": {"degree": 0.8, "betweenness": 0.6, "pagerank": 0.4},
            "explanation": "upstream",
        },
    ])

    patterns = asyncio.run(service.get_case_patterns("case-1"))
    centrality = asyncio.run(service.get_entity_centrality(entity.id))

    assert patterns is not None
    assert patterns.patterns[0].supporting_entity_ids == [entity.id]
    assert centrality is not None
    assert centrality.entity_id == entity.id
    assert service._request.await_args_list == [
        call("GET", "/patterns/case-1"),
        call("GET", f"/centrality/{graph_id}"),
    ]


def test_graph_integration_scopes_link_predictions_to_local_entities():
    source = SimpleNamespace(
        id="local-source", name="Source", entity_type=SimpleNamespace(value="PERSON"),
    )
    target = SimpleNamespace(
        id="local-target", name="Target", entity_type=SimpleNamespace(value="PHONE_NUMBER"),
    )
    neighbor = SimpleNamespace(
        id="local-neighbor", name="Neighbor", entity_type=SimpleNamespace(value="VEHICLE"),
    )
    entity_repo = AsyncMock()
    entity_repo.list_by_case.return_value = ([source, target, neighbor], 3)
    service = IntegratedGraphService(ent_repo=entity_repo, rel_repo=AsyncMock())
    source_graph_id = service._graph_entity_id(source)
    target_graph_id = service._graph_entity_id(target)
    neighbor_graph_id = service._graph_entity_id(neighbor)
    service._request = AsyncMock(return_value={
        "predictions": [{
            "source_entity_id": source_graph_id,
            "target_entity_id": target_graph_id,
            "confidence": 0.62,
            "common_neighbor_ids": [neighbor_graph_id],
            "explanation": "raw graph explanation",
            "method": "jaccard_plus_adamic_adar",
            "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
        }, {
            "source_entity_id": source_graph_id,
            "target_entity_id": "outside-this-case",
            "confidence": 0.99,
            "common_neighbor_ids": [],
            "explanation": "must not cross the case boundary",
        }],
    })

    candidates = asyncio.run(service.get_case_link_predictions("case-1"))

    assert candidates is not None
    assert len(candidates) == 1
    assert candidates[0].source_entity_id == source.id
    assert candidates[0].target_entity_id == target.id
    assert candidates[0].common_neighbor_ids == [neighbor.id]
    assert service._request.await_args_list == [
        call("GET", "/link-predictions", params={"limit": 100}),
    ]


def test_case_insights_enforces_access_before_graph_calls(
    client, admin_auth_headers, investigator_auth_headers,
):
    from app.main import app

    hidden = _case(client, admin_auth_headers, "Hidden insights case")
    graph = AsyncMock()
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(
            f"/api/v1/cases/{hidden}/insights", headers=investigator_auth_headers,
        )
        assert response.status_code == 403
        graph.get_case_patterns.assert_not_called()
        graph.get_entity_centrality.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_case_insights_filters_hidden_patterns_masks_victims_and_ranks_people(
    client, admin_auth_headers, investigator_auth_headers,
):
    from app.main import app

    own = _case(client, investigator_auth_headers, "Visible insights case")
    related = _case(client, investigator_auth_headers, "Visible linked insights case")
    hidden = _case(client, admin_auth_headers, "Hidden linked insights case")
    victim = client.post(
        f"/api/v1/cases/{own}/entities", headers=investigator_auth_headers,
        json={
            "name": "Protected Complainant", "entity_type": "PERSON",
            "properties": {"privacy_classification": "VICTIM_PII"},
        },
    ).json()
    person = client.post(
        f"/api/v1/cases/{own}/entities", headers=investigator_auth_headers,
        json={"name": "Observed Contact", "entity_type": "PERSON"},
    ).json()
    graph = AsyncMock()
    graph.get_case_patterns.return_value = {
        "case_id": own,
        "patterns": [
            {
                "pattern_type": "REPEATED_IDENTIFIER", "case_ids": [own, related],
                "confidence": 0.8, "supporting_entity_ids": [],
                "explanation": "raw upstream narrative",
                "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            },
            {
                "pattern_type": "BRIDGE_ENTITY", "case_ids": [own, hidden],
                "confidence": 0.9, "supporting_entity_ids": [],
                "explanation": "restricted upstream narrative",
                "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            },
        ],
    }
    graph.get_case_link_predictions.return_value = []
    graph.get_case_link_predictions.return_value = [{
        "source_entity_id": victim["id"],
        "target_entity_id": person["id"],
        "confidence": 0.65,
        "common_neighbor_ids": [person["id"]],
        "explanation": "raw candidate explanation",
        "method": "jaccard_plus_adamic_adar",
        "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
    }]
    graph.get_entity_centrality.side_effect = [
        CentralityResponse(
            entity_id=victim["id"],
            centrality=CentralityMetrics(degree=0.9, betweenness=0.8, pagerank=0.7),
            explanation="upstream",
        ),
        CentralityResponse(
            entity_id=person["id"],
            centrality=CentralityMetrics(degree=0.5, betweenness=0.2, pagerank=0.3),
            explanation="upstream",
        ),
    ]
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(
            f"/api/v1/cases/{own}/insights", headers=investigator_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "complete"
        assert len(data["patterns"]) == 1
        assert data["patterns"][0]["case_ids"] == [own, related]
        assert len(data["link_candidates"]) == 1
        assert data["link_candidates"][0]["source_name"] == "[VICTIM DATA MASKED]"
        assert data["link_candidates"][0]["target_name"] == "Observed Contact"
        assert "raw upstream narrative" not in response.text
        assert "raw candidate explanation" not in response.text
        assert "restricted upstream narrative" not in response.text
        assert [item["entity_id"] for item in data["influential_people"]] == [
            victim["id"], person["id"],
        ]
        assert data["influential_people"][0]["name"] == "[VICTIM DATA MASKED]"
        assert data["influential_people"][0]["is_masked"] is True
        assert "guilt" in data["disclaimer"].lower()
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_case_insights_reports_safe_upstream_failures(client, admin_auth_headers):
    from app.main import app

    case_id = _case(client, admin_auth_headers, "Unavailable insights case")
    graph = AsyncMock()
    graph.get_case_patterns.return_value = None
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(
            f"/api/v1/cases/{case_id}/insights", headers=admin_auth_headers,
        )
        assert response.status_code == 503
        assert response.json()["detail"] == "Case insights are temporarily unavailable."
        graph.get_entity_centrality.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_graph_service, None)


def test_case_insights_degrades_without_exposing_upstream_error(
    client, admin_auth_headers,
):
    from app.main import app

    case_id = _case(client, admin_auth_headers, "Partial insights case")
    client.post(
        f"/api/v1/cases/{case_id}/entities", headers=admin_auth_headers,
        json={"name": "Person with stale graph record", "entity_type": "PERSON"},
    )
    graph = AsyncMock()
    graph.get_case_patterns.return_value = {"case_id": case_id, "patterns": []}
    graph.get_case_link_predictions.return_value = []
    graph.get_entity_centrality.side_effect = RuntimeError("private upstream detail")
    app.dependency_overrides[get_graph_service] = lambda: graph
    try:
        response = client.get(
            f"/api/v1/cases/{case_id}/insights", headers=admin_auth_headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "degraded"
        assert response.json()["influential_people"] == []
        assert "private upstream detail" not in response.text
    finally:
        app.dependency_overrides.pop(get_graph_service, None)
