import io


def test_upload_document_success(client, admin_auth_headers):
    # Get a valid case_id
    cases_resp = client.post("/api/v1/cases", json={"title": "Test Case"}, headers=admin_auth_headers)
    case_id = cases_resp.json()["id"]

    file_content = b"Confidential Suspect Financial Logs\nAccount Transfer $500,000"
    file_obj = io.BytesIO(file_content)

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("evidence_log.txt", file_obj, "text/plain")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["original_filename"] == "evidence_log.txt"
    assert data["file_type"] == "txt"
    assert data["processing_status"] == "PENDING"
    assert data["case_id"] == case_id


def test_upload_document_invalid_extension(client, admin_auth_headers):
    cases_resp = client.post("/api/v1/cases", json={"title": "Test Case"}, headers=admin_auth_headers)
    case_id = cases_resp.json()["id"]

    file_content = b"Malicious executable"
    file_obj = io.BytesIO(file_content)

    response = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("virus.exe", file_obj, "application/octet-stream")},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400
    assert "Unsupported file format" in response.json()["detail"]


def test_trigger_document_ai_processing(client, admin_auth_headers):
    cases_resp = client.post("/api/v1/cases", json={"title": "Test Case"}, headers=admin_auth_headers)
    case_id = cases_resp.json()["id"]

    upload_resp = client.post(
        f"/api/v1/cases/{case_id}/documents",
        files={"file": ("transcript.pdf", io.BytesIO(b"Intercepted Call Transcript"), "application/pdf")},
        headers=admin_auth_headers,
    )
    doc_id = upload_resp.json()["id"]

    proc_resp = client.post(
        f"/api/v1/documents/{doc_id}/process",
        headers=admin_auth_headers,
    )
    assert proc_resp.status_code == 200
    assert proc_resp.json()["success"] is True

    status_resp = client.get(
        f"/api/v1/documents/{doc_id}/processing-status",
        headers=admin_auth_headers,
    )
    assert status_resp.status_code == 200
    assert status_resp.json()["document_id"] == doc_id
