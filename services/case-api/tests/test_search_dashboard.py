def test_search_and_dashboard_endpoints(client, admin_auth_headers):
    # 1. Search cases
    search_c = client.get("/api/v1/search/cases?q=Operation", headers=admin_auth_headers)
    assert search_c.status_code == 200
    assert "items" in search_c.json()

    # 2. Search entities
    search_e = client.get("/api/v1/search/entities?q=Suspect", headers=admin_auth_headers)
    assert search_e.status_code == 200
    assert "items" in search_e.json()

    # 3. Global search
    global_s = client.get("/api/v1/search/global?q=Operation", headers=admin_auth_headers)
    assert global_s.status_code == 200
    g_data = global_s.json()
    assert "results" in g_data
    assert "cases" in g_data["results"]

    # 4. Dashboard summary
    summary_resp = client.get("/api/v1/dashboard/summary", headers=admin_auth_headers)
    assert summary_resp.status_code == 200
    s_data = summary_resp.json()
    assert "total_cases" in s_data
    assert "total_entities" in s_data
    assert "total_documents" in s_data
    assert "total_relationships" in s_data

    # 5. Dashboard statistics
    stats_resp = client.get("/api/v1/dashboard/statistics", headers=admin_auth_headers)
    assert stats_resp.status_code == 200
    st_data = stats_resp.json()
    assert "cases_by_status" in st_data
    assert "entities_by_type" in st_data
    assert "relationships_by_type" in st_data
