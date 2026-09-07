"""End-to-end integration tests for CrimeLensAI Audit Trail & Hash-Chain Ledger."""

import pytest
from app.repositories.registry import case_repository, entity_repository, relationship_repository
from app.repositories.synthetic_loader import synthetic_loader


@pytest.fixture(autouse=True)
def seed_data():
    synthetic_loader.load_if_needed(case_repository, entity_repository, relationship_repository)


def test_audit_chain_listing(client, admin_auth_headers):
    # Test global chain
    res = client.get("/api/v1/ledger/chain", headers=admin_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) > 0
    first = data["items"][0]
    assert "id" in first
    assert "sequence" in first
    assert "dataHash" in first
    assert "previous_hash" in first


def test_audit_chain_filtered_by_case(client, admin_auth_headers):
    res = client.get("/api/v1/ledger/chain?case_id=DEMO-FIR-001", headers=admin_auth_headers)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] > 0
    assert len(data["items"]) > 0


def test_audit_verification_intact(client, admin_auth_headers):
    chain_res = client.get("/api/v1/ledger/chain?case_id=DEMO-FIR-001", headers=admin_auth_headers)
    assert chain_res.status_code == 200
    first_record = chain_res.json()["items"][0]

    verify_res = client.get(f"/api/v1/ledger/verify/{first_record['id']}", headers=admin_auth_headers)
    assert verify_res.status_code == 200
    verification = verify_res.json()
    assert verification["verified"] is True
    assert verification["status"] == "VERIFIED"
    assert verification["checked_records"] > 0
    assert verification["error_sequence"] is None


def test_evidence_report_export(client, admin_auth_headers):
    res = client.get("/api/v1/cases/DEMO-FIR-001/evidence-report.pdf", headers=admin_auth_headers)
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert "X-Report-SHA256" in res.headers
    assert "X-Audit-Event-ID" in res.headers
    assert len(res.content) > 1000
