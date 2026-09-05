import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

os.environ.setdefault("SERVICE_AUTH_TOKEN", "case-api-test-service-token-26189")

from app.core.config import settings
from app.main import app
from app.repositories.postgres import get_engine

TEST_URL = os.getenv("CASE_API_TEST_POSTGRES_URL")


@pytest.fixture
def database(monkeypatch):
    if not TEST_URL:
        pytest.skip("Requires isolated PostgreSQL integration database")
    url = make_url(TEST_URL)
    if url.database != "crimelens_verify":
        pytest.fail("Integration fixtures require the isolated crimelens_verify database")
    schema = "case_audit_test_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as connection:
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    scoped = url.update_query_dict({"options": f"-csearch_path={schema},public"})
    monkeypatch.setattr(settings, "DATABASE_URL", scoped.render_as_string(hide_password=False))
    get_engine.cache_clear()
    engine = get_engine()
    raw = engine.raw_connection()
    try:
        raw.driver_connection.autocommit = True
        with raw.cursor() as cursor:
            cursor.execute(Path("/database/schema.sql").read_text())
            cursor.execute(
                "INSERT INTO users(id,email,password_hash,full_name,role) VALUES "
                "('test-admin','admin@test.example','not-a-login-password','Test Admin','ADMIN')"
            )
            cursor.execute(Path("/database/migrations/001_audit_outbox.sql").read_text())
            cursor.execute(Path("/database/migrations/002_structured_ingestion.sql").read_text())
            cursor.execute(Path("/database/migrations/003_runtime_roles.sql").read_text())
    finally:
        raw.driver_connection.autocommit = False
        raw.close()
    try:
        yield engine
    finally:
        engine.dispose()
        get_engine.cache_clear()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


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
    return {"Authorization": f"Bearer {token}", "X-Service-Token": settings.SERVICE_AUTH_TOKEN}


@pytest.fixture(scope="module")
def investigator_auth_headers(client, admin_auth_headers):
    # Register and login a fresh test investigator
    register_resp = client.post(
        "/api/v1/auth/register",
        headers=admin_auth_headers,
        json={
            "email": "test_investigator@crimelens.ai",
            "password": "TestPassword123!",
            "full_name": "Test Officer",
            "badge_number": "BADGE-999",
        },
    )
    assert register_resp.status_code in [201, 409]

    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "test_investigator@crimelens.ai", "password": "TestPassword123!"},
    )
    assert login_resp.status_code == 200
    token = login_resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "X-Service-Token": settings.SERVICE_AUTH_TOKEN}
