def test_create_case(client, admin_auth_headers):
    response = client.post(
        "/api/v1/cases",
        json={
            "title": "Operation Golden Syndicate",
            "description": "Counter-narcotics and illegal asset tracking operation.",
            "priority": "HIGH",
            "tags": ["narcotics", "laundering"],
        },
        headers=admin_auth_headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Operation Golden Syndicate"
    assert data["status"] == "OPEN"
    assert "case_number" in data


def test_list_cases(client, admin_auth_headers):
    response = client.get("/api/v1/cases", headers=admin_auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert data["total"] >= 1


def test_get_case_detail(client, admin_auth_headers):
    # Get sample case
    list_resp = client.get("/api/v1/cases", headers=admin_auth_headers)
    case_id = list_resp.json()["items"][0]["id"]

    response = client.get(f"/api/v1/cases/{case_id}", headers=admin_auth_headers)
    assert response.status_code == 200
    assert response.json()["id"] == case_id


def test_update_case_status(client, admin_auth_headers):
    list_resp = client.get("/api/v1/cases", headers=admin_auth_headers)
    case_id = list_resp.json()["items"][0]["id"]

    response = client.patch(
        f"/api/v1/cases/{case_id}/status",
        json={"status": "IN_PROGRESS"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "IN_PROGRESS"


def test_delete_case(client, admin_auth_headers):
    create_resp = client.post(
        "/api/v1/cases",
        json={"title": "Temporary Case to Delete", "description": "To be removed."},
        headers=admin_auth_headers,
    )
    case_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/v1/cases/{case_id}", headers=admin_auth_headers)
    assert del_resp.status_code == 204

    get_resp = client.get(f"/api/v1/cases/{case_id}", headers=admin_auth_headers)
    assert get_resp.status_code == 404
