"""Audit gateway authorization, unverified defaults, and upstream failure handling."""

import httpx
import pytest

from app.core.config import settings
from app.integrations.ledger_integration import LedgerService, get_ledger_service
from app.main import app


@pytest.fixture
def audit_transport(monkeypatch):
    monkeypatch.setattr(settings, "SERVICE_AUTH_TOKEN", "test-audit-client-token-" + "x" * 40)
    handlers = []
    requests = []

    def dispatch(request):
        requests.append(request)
        assert request.headers["X-Service-Token"] == settings.SERVICE_AUTH_TOKEN
        return handlers[-1](request)

    service = LedgerService(transport=httpx.MockTransport(dispatch))
    app.dependency_overrides[get_ledger_service] = lambda: service
    yield handlers, requests
    app.dependency_overrides.pop(get_ledger_service, None)


def record(case_id="case-sample-001"):
    return {
        "id": "audit-one", "sequence": 1, "timestamp": "2026-09-04T00:00:00+00:00",
        "record_id": "entity-one", "case_id": case_id, "actor": "officer-one",
        "action": "ENTITY_CREATED", "resource_type": "ENTITY",
        "payload": {"victim_name": "Not for unrestricted disclosure"},
        "hash": "a" * 64, "previous_hash": "0" * 64,
    }


def test_chain_does_not_claim_unperformed_verification(client, admin_auth_headers, audit_transport):
    handlers, _ = audit_transport
    handlers.append(lambda _: httpx.Response(200, json={"records": [record()], "total": 1, "offset": 0, "limit": 50}))
    response = client.get("/api/v1/ledger/chain", headers=admin_auth_headers)
    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["status"] == "UNVERIFIED" and item["verified"] is None
    assert "payload" not in item
    assert "Not for unrestricted disclosure" not in response.text


@pytest.mark.parametrize("upstream,expected", [(404, 404), (500, 503), (401, 503)])
def test_unknown_or_unavailable_never_verifies(client, admin_auth_headers, audit_transport, upstream, expected):
    handlers, _ = audit_transport
    handlers.append(lambda _: httpx.Response(upstream, json={"detail": "upstream failure"}))
    response = client.get("/api/v1/ledger/verify/missing", headers=admin_auth_headers)
    assert response.status_code == expected
    assert response.json().get("verified") is not True


def test_case_filter_and_defense_against_out_of_scope_response(client, investigator_auth_headers, audit_transport):
    handlers, requests = audit_transport
    created = client.post("/api/v1/cases", headers=investigator_auth_headers, json={
        "title": "Audit scope test", "description": "Assigned investigator audit visibility",
    }).json()
    case_id = created["id"]
    handlers.append(lambda _: httpx.Response(200, json={"records": [record(case_id)], "total": 1, "offset": 0, "limit": 50}))
    path = "/api/v1/ledger/chain?case_id=" + case_id
    assert client.get(path, headers=investigator_auth_headers).status_code == 200
    assert requests[-1].url.params.get_list("case_id") == [case_id]
    handlers.append(lambda _: httpx.Response(200, json={"records": [record("unauthorized-case")], "total": 1, "offset": 0, "limit": 50}))
    assert client.get(path, headers=investigator_auth_headers).status_code == 502


def test_ledger_requires_login(client):
    assert client.get("/api/v1/ledger/chain").status_code == 401
    assert client.get("/api/v1/ledger/verify/anything").status_code == 401
