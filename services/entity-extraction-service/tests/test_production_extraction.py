"""Regressions for arbitrary narrative extraction and identifier safety."""

import pytest
from app.extractors.pipeline import run_extraction
from app.extractors.resolver import resolve_entities
from app.models.schemas import ExtractedEntityResponse


def test_extended_types_and_offsets():
    text = (
        "Complainant Anjali Gupta reported at Bengaluru on 2026-08-19. "
        "Phone +91 98765 43210; Aadhaar: 2345 6789 0123; PAN ABCDE1234F; "
        "passport P1234567; vehicle KA 01 MG 1234; UPI anjali@oksbi; "
        "bank account: 123456789012; email officer@example.org; "
        "organization North Star Trading; Section 420 IPC."
    )
    entities = run_extraction(text, "fir_text", "case-new")
    kinds = {entity.entity_type.value for entity in entities}
    assert kinds >= {
        "PERSON", "PHONE", "AADHAAR", "PAN", "PASSPORT", "VEHICLE", "UPI_ID",
        "BANK_ACCOUNT", "EMAIL", "LOCATION", "ORG", "DATE", "IPC_SECTION",
    }
    for entity in entities:
        assert text[entity.start_offset:entity.end_offset] == entity.value
        assert entity.case_id == "case-new"
    assert not any(entity.value == "919876543210" and entity.entity_type == "AADHAAR" for entity in entities)
    assert [entity.value for entity in entities if entity.entity_type == "PERSON"] == ["Anjali Gupta"]


@pytest.mark.parametrize("kind,first,second", [
    ("PAN", "ABCDE1234F", "ABCDE1235F"),
    ("PASSPORT", "P1234567", "P1234568"),
    ("BANK_ACCOUNT", "123456789012", "123456789013"),
    ("AADHAAR", "234567890123", "234567890124"),
    ("EMAIL", "officer1@example.org", "officer2@example.org"),
])
def test_identifiers_never_fuzzy_merge(kind, first, second):
    mentions = [ExtractedEntityResponse(
        entity_id=str(index), entity_type=kind, value=value, normalized_value=value,
        confidence=.9, start_offset=0, end_offset=len(value), source_field="fir_text",
    ) for index, value in enumerate([first, second])]
    assert len(resolve_entities(mentions)) == 2


def test_batch_rejects_blank_and_excessive_aggregate(client):
    assert client.post("/api/v1/extract/batch", json={"firs": [{"case_id": "c", "raw_text": "  "}]}).status_code == 422
    response = client.post("/api/v1/extract/batch", json={"firs": [
        {"case_id": str(index), "raw_text": "a" * 500_000} for index in range(5)
    ]})
    assert response.status_code == 422


def test_fallback_disclosed_without_overclaiming(client, monkeypatch):
    from app.api import routes
    monkeypatch.setattr(routes, "loaded_model_name", lambda: "blank_en_fallback")
    result = client.post("/api/v1/extract", json={"text": "Phone 9876543210"}).json()
    assert result["model"] == "blank_en_fallback"
    assert any("coverage is limited" in warning for warning in result["warnings"])
    assert any("not calibrated" in warning for warning in result["warnings"])
