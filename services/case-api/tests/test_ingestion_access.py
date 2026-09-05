from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import ingestion
from tests.test_linkage_access import create_case


@pytest.mark.parametrize("operation", ["csv", "records", "status", "source"])
def test_structured_routes_require_case_assignment(client, admin_auth_headers, investigator_auth_headers, monkeypatch, operation):
    case_id = create_case(client, admin_auth_headers, "Restricted structured evidence")
    validate = AsyncMock()
    monkeypatch.setattr(ingestion, "validate_evidence", validate)
    base = f"/api/v1/cases/{case_id}/ingestion"
    if operation == "csv":
        response = client.post(base + "/csv?kind=cdr", headers=investigator_auth_headers, files={"file": ("calls.csv", b"invalid")})
    elif operation == "records":
        response = client.post(base + "/records", headers=investigator_auth_headers, json={"kind": "cdr", "records": [{}]})
    else:
        response = client.get(base + "/batch-id" + ("/source" if operation == "source" else ""), headers=investigator_auth_headers)
    assert response.status_code == 403
    validate.assert_not_called()


def test_rejects_invalid_encoding_before_validation_or_storage(client, investigator_auth_headers, monkeypatch):
    case_id = create_case(client, investigator_auth_headers, "Invalid structured encoding")
    validate = AsyncMock()
    monkeypatch.setattr(ingestion, "validate_evidence", validate)
    response = client.post(f"/api/v1/cases/{case_id}/ingestion/csv?kind=cdr", headers=investigator_auth_headers, files={"file": ("evidence.csv", b"\xff\xfe")})
    assert response.status_code == 422
    validate.assert_not_called()


def test_nonfinite_json_rejected_without_internal_error(client, investigator_auth_headers, monkeypatch):
    case_id = create_case(client, investigator_auth_headers, "Invalid amount input")
    validate = AsyncMock()
    monkeypatch.setattr(ingestion, "validate_evidence", validate)
    response = client.post(f"/api/v1/cases/{case_id}/ingestion/records", headers={**investigator_auth_headers, "Content-Type": "application/json"},
                           content='{"kind":"transactions","records":[{"amount":NaN}]}')
    assert response.status_code == 422
    validate.assert_not_called()


def test_unauthed_import_never_reaches_validation(client, monkeypatch):
    validate = AsyncMock()
    monkeypatch.setattr(ingestion, "validate_evidence", validate)
    response = client.post("/api/v1/cases/case-1/ingestion/csv?kind=cdr", files={"file": ("evidence.csv", b"source")})
    assert response.status_code == 401
    validate.assert_not_called()


def test_assigned_analyst_cannot_write_evidence(client, investigator_auth_headers, monkeypatch):
    from app.api.deps import get_current_user
    from app.main import app
    from app.schemas.user import UserResponse

    case_id = create_case(client, investigator_auth_headers, "Read-only assigned analyst")
    user = client.get("/api/v1/auth/me", headers=investigator_auth_headers).json()
    user["role"] = "ANALYST"
    validate = AsyncMock()
    monkeypatch.setattr(ingestion, "validate_evidence", validate)
    app.dependency_overrides[get_current_user] = lambda: UserResponse(**user)
    try:
        response = client.post(f"/api/v1/cases/{case_id}/ingestion/records", json={"kind": "cdr", "records": [{}]})
        assert response.status_code == 403
        assert "read-only" in response.json()["detail"]
        validate.assert_not_called()
    finally:
        app.dependency_overrides.pop(get_current_user, None)
