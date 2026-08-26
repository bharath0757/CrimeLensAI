def test_graph_endpoints(client, admin_auth_headers):
    # 1. Setup case with entities and relationships
    case_resp = client.post(
        "/api/v1/cases",
        json={"title": "Graph Analytics Case", "description": "Testing network topology"},
        headers=admin_auth_headers,
    )
    case_id = case_resp.json()["id"]

    e1 = client.post(f"/api/v1/cases/{case_id}/entities", json={"name": "Suspect A", "entity_type": "PERSON"}, headers=admin_auth_headers).json()["id"]
    e2 = client.post(f"/api/v1/cases/{case_id}/entities", json={"name": "Suspect B", "entity_type": "PERSON"}, headers=admin_auth_headers).json()["id"]
    e3 = client.post(f"/api/v1/cases/{case_id}/entities", json={"name": "Offshore Bank", "entity_type": "BANK_ACCOUNT"}, headers=admin_auth_headers).json()["id"]

    client.post(f"/api/v1/cases/{case_id}/relationships", json={"source_entity_id": e1, "target_entity_id": e2, "relationship_type": "COMMUNICATED_WITH"}, headers=admin_auth_headers)
    client.post(f"/api/v1/cases/{case_id}/relationships", json={"source_entity_id": e2, "target_entity_id": e3, "relationship_type": "TRANSFERRED_FUNDS"}, headers=admin_auth_headers)

    # 2. Get full graph topology
    graph_resp = client.get(f"/api/v1/cases/{case_id}/graph", headers=admin_auth_headers)
    assert graph_resp.status_code == 200
    g_data = graph_resp.json()
    assert len(g_data["nodes"]) == 3
    assert len(g_data["edges"]) == 2

    # 3. Get entity connections
    conn_resp = client.get(f"/api/v1/entities/{e1}/connections", headers=admin_auth_headers)
    assert conn_resp.status_code == 200
    assert conn_resp.json()["connections_count"] == 1

    # 4. Get entity neighbors
    neigh_resp = client.get(f"/api/v1/entities/{e1}/neighbors?depth=2", headers=admin_auth_headers)
    assert neigh_resp.status_code == 200
    assert len(neigh_resp.json()["nodes"]) == 3

    # 5. Get graph stats
    stats_resp = client.get(f"/api/v1/cases/{case_id}/graph/stats", headers=admin_auth_headers)
    assert stats_resp.status_code == 200
    assert stats_resp.json()["total_nodes"] == 3
    assert stats_resp.json()["total_edges"] == 2

    # 6. Get shortest path algorithm between e1 and e3
    path_resp = client.get(
        f"/api/v1/cases/{case_id}/graph/shortest-path?source_entity_id={e1}&target_entity_id={e3}",
        headers=admin_auth_headers,
    )
    assert path_resp.status_code == 200
    p_data = path_resp.json()
    assert p_data["path_found"] is True
    assert p_data["hop_count"] == 2
    assert len(p_data["nodes"]) == 3
