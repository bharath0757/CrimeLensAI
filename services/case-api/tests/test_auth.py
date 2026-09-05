def test_register_user_success(client, admin_auth_headers):
    response = client.post(
        "/api/v1/auth/register",
        headers=admin_auth_headers,
        json={
            "email": "new_detective@crimelens.ai",
            "password": "SecurePassword123!",
            "full_name": "Detective Miller",
            "badge_number": "BADGE-404",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "new_detective@crimelens.ai"
    assert data["full_name"] == "Detective Miller"
    assert "password" not in data


def test_register_duplicate_email(client, admin_auth_headers):
    response = client.post(
        "/api/v1/auth/register",
        headers=admin_auth_headers,
        json={
            "email": "admin@crimelens.ai",
            "password": "Password123!",
            "full_name": "Duplicate Admin",
        },
    )
    assert response.status_code == 409
    assert "already exists" in response.json()["detail"]


def test_login_success(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crimelens.ai", "password": "AdminSecret123!"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@crimelens.ai"


def test_login_invalid_password(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@crimelens.ai", "password": "WrongPassword!"},
    )
    assert response.status_code == 401


def test_read_me_authenticated(client, admin_auth_headers):
    response = client.get("/api/v1/auth/me", headers=admin_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "admin@crimelens.ai"


def test_read_me_unauthenticated(client):
    response = client.get("/api/v1/auth/me")
    assert response.status_code == 401
