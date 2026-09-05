import os
from unittest.mock import patch

import pytest
from app.models import ValidationRequest
from app.parsers.structured import validate
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app

CDR = {"cdr_id": "CALL-1", "caller": "+91 90009 90189", "receiver": "9000990190", "timestamp": "2026-09-04T13:00:00+05:30", "duration": "45", "tower": "TOWER-01", "imei": "860000000000001"}
TX = {"transaction_id": "TX-1", "sender": "510000000001", "receiver": "510000000002", "amount": "123.45", "upi": "demo.01@upi", "timestamp": "2026-09-04T12:00:00Z"}


def result(kind="cdr", records=None, csv_text=None):
    return validate(ValidationRequest(kind=kind, case_id="case-1", records=records, csv_text=csv_text))


def test_normalizes_phone_and_timezone_and_retains_row_reference():
    record = result(records=[CDR]).records[0]
    assert record.source == "9000990189"
    assert record.source_type == "PHONE_NUMBER"
    assert record.timestamp.isoformat() == "2026-09-04T07:30:00+00:00"
    assert record.row_number == 1


def test_bom_and_uppercase_csv_headers():
    value = "\ufeffCALLER,RECEIVER,TIMESTAMP,DURATION,TOWER,IMEI\r\n9000990189,9000990190,2026-09-04T12:00:00Z,45,TOWER-01,860000000000001\r\n"
    parsed = result(csv_text=value)
    assert parsed.records[0].row_number == 2
    assert parsed.records[0].record_id.startswith("derived-cdr-")
    assert parsed.warnings


@pytest.mark.parametrize("field,value", [("caller", "invalid"), ("imei", "123"), ("duration", "-1"), ("duration", "3.14"), ("timestamp", "2026-09-04T12:00:00"), ("case_id", "other-case")])
def test_rejects_bad_cdr_field(field, value):
    with pytest.raises(HTTPException) as failure:
        result(records=[CDR | {field: value}])
    assert failure.value.status_code == 422


@pytest.mark.parametrize("amount", ["0", "-2", "12.345", "NaN", "Infinity", "1000000000000.00"])
def test_rejects_invalid_money(amount):
    with pytest.raises(HTTPException):
        result("transactions", records=[TX | {"amount": amount}])


def test_upi_sender_is_not_misclassified_as_bank_account():
    row = result("transactions", records=[TX | {"sender": "sender.01@upi"}]).records[0]
    assert row.source_type == "UPI_ID"
    assert row.target_type == "BANK_ACCOUNT"
    assert str(row.amount) == "123.45"


def test_duplicate_id_dedupes_only_identical_content():
    assert result(records=[CDR, CDR]).duplicate_rows == 1
    with pytest.raises(HTTPException, match="conflicting contents"):
        result(records=[CDR, CDR | {"duration": "46"}])


@pytest.mark.parametrize("csv_text", ["", "caller,caller\n1,2", "caller,receiver,timestamp,duration,tower,imei\n1,2,3", 'caller,receiver\n"unterminated'])
def test_malformed_csv_rejected(csv_text):
    with pytest.raises(HTTPException):
        result(csv_text=csv_text)


def test_internal_endpoint_requires_configured_service_credentials(monkeypatch):
    monkeypatch.setenv("SERVICE_AUTH_TOKEN", "isolated-ingestion-test-service-token-26189")
    with TestClient(app) as client:
        payload = {"kind": "cdr", "case_id": "case-1", "records": [CDR]}
        assert client.post("/api/v1/validate", json=payload).status_code == 401
        response = client.post("/api/v1/validate", json=payload, headers={"X-Service-Token": "isolated-ingestion-test-service-token-26189"})
        assert response.status_code == 200
        assert response.json()["records"][0]["source"] == "9000990189"


@pytest.mark.parametrize("change", [{"transaction_id": " "}, {"cdr_id": "call-1"}, {"transaction_id": None}, {"sender": []}, {"amount": True}])
def test_transaction_rejects_missing_identity_and_non_scalar_fields(change):
    with pytest.raises(HTTPException) as failure:
        result("transactions", records=[TX | change])
    assert failure.value.status_code == 422


def test_preserves_optional_transaction_metadata():
    row = result("transactions", records=[TX | {"transaction_type": "UPI", "description": "Synthetic linked transfer"}]).records[0]
    assert row.transaction_type == "UPI"
    assert row.description == "Synthetic linked transfer"


def test_legacy_ingestion_missing_bearer_is_unauthorized():
    with (
        patch.dict(os.environ, {"SERVICE_AUTH_TOKEN": "isolated-ingestion-test-service-token-26189"}),
        TestClient(app) as client,
    ):
        response = client.post("/api/v1/ingest/transactions", json={"transaction_id": "TX-1", "case_id": "case-1", "timestamp": TX["timestamp"], "sender_upi": "sender@upi", "receiver_upi": "receiver@upi", "amount": "1.00"})
    assert response.status_code == 401
