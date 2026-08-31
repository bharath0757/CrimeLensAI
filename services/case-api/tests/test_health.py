from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check_endpoint():
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "CrimeLens AI" in data["app"]
    assert "message" in data
    assert data["message"] == "CrimeLens AI backend is operating normally."
