"""Evidence ownership checks must apply to reads, processing, and writes."""

import pytest


@pytest.mark.parametrize("operation", ["metadata", "status", "list", "process", "delete", "upload"])
def test_unassigned_officer_cannot_access_evidence(client, admin_auth_headers, investigator_auth_headers, operation):
    created = client.post("/api/v1/cases", headers=admin_auth_headers, json={
        "title": "Restricted evidence", "description": "Case assignment authorization test",
    })
    assert created.status_code == 201
    case_id = created.json()["id"]
    uploaded = client.post(f"/api/v1/cases/{case_id}/documents", headers=admin_auth_headers,
                           files={"file": ("private.txt", b"Restricted FIR text", "text/plain")})
    assert uploaded.status_code == 201
    doc_id = uploaded.json()["id"]
    path = f"/api/v1/documents/{doc_id}"
    if operation == "metadata":
        response = client.get(path, headers=investigator_auth_headers)
    elif operation == "status":
        response = client.get(path + "/processing-status", headers=investigator_auth_headers)
    elif operation == "list":
        response = client.get(f"/api/v1/cases/{case_id}/documents", headers=investigator_auth_headers)
    elif operation == "process":
        response = client.post(path + "/process", headers=investigator_auth_headers)
    elif operation == "delete":
        response = client.delete(path, headers=investigator_auth_headers)
    else:
        response = client.post(f"/api/v1/cases/{case_id}/documents", headers=investigator_auth_headers,
                               files={"file": ("injected.txt", b"Injected evidence", "text/plain")})
    assert response.status_code == 403
    assert client.get(path, headers=admin_auth_headers).status_code == 200
