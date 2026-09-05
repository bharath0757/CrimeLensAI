from datetime import timedelta
from unittest.mock import AsyncMock

import jwt
import pytest
from pydantic import ValidationError

from app.api.deps import get_user_repository
from app.core.config import Settings, settings
from app.core.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
)
from app.main import app
from app.schemas.user import UserResponse


@pytest.mark.parametrize("authenticated", [False, True])
def test_only_administrators_can_provision_accounts(client, investigator_auth_headers, authenticated):
    response = client.post("/api/v1/auth/register", headers=investigator_auth_headers if authenticated else {},
                           json={"email": "unauthorized@example.com", "password": "LongEnoughPassword!", "full_name": "Unauthorized Provision", "role": "ADMIN"})
    assert response.status_code == (403 if authenticated else 401)


@pytest.mark.parametrize("path", ["json", "form"])
def test_disabled_officer_cannot_receive_token(client, path):
    repository = AsyncMock()
    repository.get_by_email.return_value = UserResponse(id="inactive", email="inactive@example.com", full_name="Inactive Officer", is_active=False, role="INVESTIGATOR", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
    repository.get_password_hash.return_value = get_password_hash("Valid-password-123!")
    app.dependency_overrides[get_user_repository] = lambda: repository
    try:
        if path == "json":
            response = client.post("/api/v1/auth/login", json={"email": "inactive@example.com", "password": "Valid-password-123!"})
        else:
            response = client.post("/api/v1/auth/login/form", data={"username": "inactive@example.com", "password": "Valid-password-123!"})
        assert response.status_code == 401
        assert "access_token" not in response.json()
    finally:
        app.dependency_overrides.pop(get_user_repository, None)


@pytest.mark.parametrize("claim", ["exp", "sub", "iat", "iss", "aud", "jti"])
def test_tokens_missing_required_claims_are_rejected(client, claim):
    payload = decode_access_token(create_access_token("user-admin-001"))
    del payload[claim]
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("claim", ["iss", "aud"])
def test_other_app_tokens_are_rejected(client, claim):
    payload = decode_access_token(create_access_token("user-admin-001"))
    payload[claim] = "different-application"
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm="HS256")
    assert client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_token_and_reserved_claim_override():
    with pytest.raises(Exception, match="expired"):
        decode_access_token(create_access_token("officer", expires_delta=timedelta(seconds=-1)))
    with pytest.raises(ValueError, match="override"):
        create_access_token("officer", extra_claims={"exp": 9999999999})


@pytest.mark.parametrize("password", ["short", "密" * 30])
def test_registration_password_is_validated_before_bcrypt(client, admin_auth_headers, password):
    response = client.post("/api/v1/auth/register", headers=admin_auth_headers,
                           json={"email": "invalid-password@example.com", "password": password, "full_name": "Password Validation"})
    assert response.status_code == 422
    assert any(error["loc"][-1] == "password" for error in response.json()["detail"])


@pytest.mark.parametrize("overrides", [{"SECRET_KEY": "change-this-in-production"}, {"DATA_BACKEND": "memory"}, {"SERVICE_AUTH_TOKEN": ""}, {"DEBUG": True}, {"ALLOWED_ORIGINS": ["*"]}])
def test_production_rejects_insecure_configuration(overrides):
    values = {"ENVIRONMENT": "production", "SECRET_KEY": "isolated-test-signing-key-at-least-32-bytes", "DATA_BACKEND": "postgres", "SERVICE_AUTH_TOKEN": "isolated-service-test-token-at-least-32-bytes"}
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **(values | overrides))


def test_production_cannot_use_an_automatic_development_signing_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValidationError, match="explicit SECRET_KEY"):
        Settings(_env_file=None, ENVIRONMENT="production", DATA_BACKEND="postgres", SERVICE_AUTH_TOKEN="isolated-service-test-token-at-least-32-bytes")
