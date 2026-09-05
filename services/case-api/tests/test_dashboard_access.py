def test_dashboard_metrics_require_officer_authentication(client):
    for endpoint in ("stats", "summary", "statistics", "overview", "alerts"):
        response = client.get(f"/api/v1/dashboard/{endpoint}")
        assert response.status_code == 401
