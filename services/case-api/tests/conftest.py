import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def admin_auth_headers(client):
    # Log in as seed admin
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crimelens.ai", "password": "AdminSecret123!"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def investigator_auth_headers(client):
    # Register and login a fresh test investigator
    register_resp = client.post(
        "/api/v1/auth/register",
        json={
            "email": "test_investigator@crimelens.ai",
            "password": "TestPassword123!",
            "full_name": "Test Officer",
            "badge_number": "BADGE-999",
        },
    )
    assert register_resp.status_code in [201, 400]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_investigator@crimelens.ai", "password": "TestPassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
