def test_search_and_dashboard_endpoints(client, admin_auth_headers):
    # 1. Search cases
    search_c = client.get("/api/v1/search?q=Operation", headers=admin_auth_headers)
    assert search_c.status_code == 200
    assert "cases" in search_c.json()

    # 4. Dashboard summary
    summary_resp = client.get("/api/v1/dashboard/stats", headers=admin_auth_headers)
    assert summary_resp.status_code == 200
    s_data = summary_resp.json()
    assert "total_cases" in s_data
    assert "total_entities" in s_data
