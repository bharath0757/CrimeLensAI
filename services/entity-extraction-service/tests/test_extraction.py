"""
CrimeLensAI — Extraction Service Tests
========================================
Comprehensive, deterministic tests for entity extraction, normalization,
offset traceability, entity resolution, and error handling.

All tests use realistic FIR-style text.
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture(scope="module")
def client():
    token = "extraction-test-service-token-26189"
    with (
        patch.dict(os.environ, {"SERVICE_AUTH_TOKEN": token}),
        TestClient(app, headers={"X-Service-Token": token}) as c,
    ):
        yield c


# Realistic FIR text containing multiple entity types
FIR_TEXT = (
    "On 15th January 2024, Rajesh Kumar (phone: +91 98765 43210) was seen "
    "near Hyderabad railway station driving vehicle AP 39 AB 1234. He was "
    "accompanied by Priya Sharma, an employee of Tata Consultancy Services. "
    "A UPI transaction was traced to rajesh@oksbi from Delhi. Another witness "
    "Suresh reported seeing the suspect at Mumbai Central on 20th January 2024. "
    "The suspect also used phone number 09876543210 and vehicle KA 01 MG 5678."
)


# ------------------------------------------------------------------
# 1. PERSON Extraction
# ------------------------------------------------------------------

class TestPersonExtraction:
    def test_extracts_person_names(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        assert resp.status_code == 200
        entities = resp.json()["entities"]
        person_values = [e["value"] for e in entities if e["entity_type"] == "PERSON"]
        # spaCy should find at least one person name
        assert len(person_values) >= 1

    def test_person_normalization(self, client: TestClient):
        text = "The accused  RAJESH  KUMAR  was arrested."
        resp = client.post("/api/v1/extract", json={"text": text})
        assert resp.status_code == 200
        entities = resp.json()["entities"]
        persons = [e for e in entities if e["entity_type"] == "PERSON"]
        for p in persons:
            # Normalized value should be lowercase, single-spaced
            assert p["normalized_value"] == p["normalized_value"].lower()
            assert "  " not in p["normalized_value"]


# ------------------------------------------------------------------
# 2. PHONE Extraction
# ------------------------------------------------------------------

class TestPhoneExtraction:
    def test_extracts_plus91_phone(self, client: TestClient):
        text = "Call him at +91 98765 43210 immediately."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        phones = [e for e in entities if e["entity_type"] == "PHONE"]
        assert len(phones) >= 1
        assert phones[0]["normalized_value"] == "+919876543210"

    def test_extracts_zero_prefix_phone(self, client: TestClient):
        text = "His number is 09876543210."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        phones = [e for e in entities if e["entity_type"] == "PHONE"]
        assert len(phones) >= 1
        assert phones[0]["normalized_value"] == "+919876543210"

    def test_extracts_bare_10digit_phone(self, client: TestClient):
        text = "Contact 9876543210 for details."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        phones = [e for e in entities if e["entity_type"] == "PHONE"]
        assert len(phones) >= 1
        assert phones[0]["normalized_value"] == "+919876543210"

    def test_phone_confidence(self, client: TestClient):
        text = "Call +91 98765 43210."
        resp = client.post("/api/v1/extract", json={"text": text})
        phones = [e for e in resp.json()["entities"] if e["entity_type"] == "PHONE"]
        assert len(phones) >= 1
        assert phones[0]["confidence"] == 0.95  # regex confidence


# ------------------------------------------------------------------
# 3. UPI Extraction
# ------------------------------------------------------------------

class TestUPIExtraction:
    def test_extracts_upi_id(self, client: TestClient):
        text = "Payment received from rajesh@oksbi for Rs 5000."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        upis = [e for e in entities if e["entity_type"] == "UPI_ID"]
        assert len(upis) == 1
        assert upis[0]["value"] == "rajesh@oksbi"
        assert upis[0]["normalized_value"] == "rajesh@oksbi"

    def test_upi_normalization_uppercase(self, client: TestClient):
        text = "UPI ID: RAJESH@OKSBI was used."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        upis = [e for e in entities if e["entity_type"] == "UPI_ID"]
        assert len(upis) == 1
        assert upis[0]["normalized_value"] == "rajesh@oksbi"

    def test_rejects_email_not_upi(self, client: TestClient):
        text = "Email: user@gmail.com is not a UPI."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        upis = [e for e in entities if e["entity_type"] == "UPI_ID"]
        assert len(upis) == 0  # gmail is not a UPI handle


# ------------------------------------------------------------------
# 4. VEHICLE Extraction
# ------------------------------------------------------------------

class TestVehicleExtraction:
    def test_extracts_vehicle_spaced(self, client: TestClient):
        text = "Vehicle number AP 39 AB 1234 was seen at the crime scene."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        vehicles = [e for e in entities if e["entity_type"] == "VEHICLE"]
        assert len(vehicles) >= 1
        assert vehicles[0]["normalized_value"] == "AP39AB1234"

    def test_extracts_vehicle_dashed(self, client: TestClient):
        text = "The car MH-12-AB-1234 fled the scene."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        vehicles = [e for e in entities if e["entity_type"] == "VEHICLE"]
        assert len(vehicles) >= 1
        assert vehicles[0]["normalized_value"] == "MH12AB1234"

    def test_extracts_vehicle_compact(self, client: TestClient):
        text = "Registration: KA01MG5678."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        vehicles = [e for e in entities if e["entity_type"] == "VEHICLE"]
        assert len(vehicles) >= 1
        assert vehicles[0]["normalized_value"] == "KA01MG5678"

    def test_rejects_non_indian_state(self, client: TestClient):
        text = "Vehicle XX 12 AB 1234 is not valid."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        vehicles = [e for e in entities if e["entity_type"] == "VEHICLE"]
        assert len(vehicles) == 0


# ------------------------------------------------------------------
# 5. LOCATION Extraction
# ------------------------------------------------------------------

class TestLocationExtraction:
    def test_extracts_location(self, client: TestClient):
        text = "The suspect was last seen in Hyderabad near Charminar."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        locations = [e for e in entities if e["entity_type"] == "LOCATION"]
        # spaCy should find at least Hyderabad
        assert len(locations) >= 1

    def test_location_normalization(self, client: TestClient):
        text = "The incident occurred in Mumbai."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        locations = [e for e in entities if e["entity_type"] == "LOCATION"]
        for loc in locations:
            # Title-cased normalization
            assert loc["normalized_value"] == loc["normalized_value"].title()


# ------------------------------------------------------------------
# 6. ORG Extraction
# ------------------------------------------------------------------

class TestOrgExtraction:
    def test_extracts_org(self, client: TestClient):
        text = "He works at Tata Consultancy Services in Bangalore."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        orgs = [e for e in entities if e["entity_type"] == "ORG"]
        assert len(orgs) >= 1


# ------------------------------------------------------------------
# 7. DATE Extraction
# ------------------------------------------------------------------

class TestDateExtraction:
    def test_extracts_date(self, client: TestClient):
        text = "The incident happened on 15th January 2024."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        dates = [e for e in entities if e["entity_type"] == "DATE"]
        assert len(dates) >= 1


# ------------------------------------------------------------------
# 8. Normalization
# ------------------------------------------------------------------

class TestNormalization:
    def test_phone_normalization_variants(self):
        from app.extractors.normalizers import normalize_phone
        assert normalize_phone("+91 98765 43210") == "+919876543210"
        assert normalize_phone("09876543210") == "+919876543210"
        assert normalize_phone("9876543210") == "+919876543210"

    def test_vehicle_normalization(self):
        from app.extractors.normalizers import normalize_vehicle
        assert normalize_vehicle("AP 39 AB 1234") == "AP39AB1234"
        assert normalize_vehicle("ka-01-mg-5678") == "KA01MG5678"

    def test_upi_normalization(self):
        from app.extractors.normalizers import normalize_upi
        assert normalize_upi("RAJESH@OKSBI") == "rajesh@oksbi"
        assert normalize_upi("  user@ybl  ") == "user@ybl"

    def test_person_normalization(self):
        from app.extractors.normalizers import normalize_person
        assert normalize_person("  RAJESH  KUMAR  ") == "rajesh kumar"

    def test_location_normalization(self):
        from app.extractors.normalizers import normalize_location
        assert normalize_location("  hyderabad  ") == "Hyderabad"

    def test_org_normalization(self):
        from app.extractors.normalizers import normalize_org
        assert normalize_org("  State  Bank of India ") == "state bank of india"


# ------------------------------------------------------------------
# 9. Source Offsets
# ------------------------------------------------------------------

class TestSourceOffsets:
    def test_offsets_match_original_text(self, client: TestClient):
        text = "Call +91 98765 43210 now."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        for ent in entities:
            start = ent["start_offset"]
            end = ent["end_offset"]
            extracted = text[start:end]
            assert extracted == ent["value"], (
                f"Offset mismatch: text[{start}:{end}] = {extracted!r} "
                f"but value = {ent['value']!r}"
            )

    def test_offsets_in_fir_text(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        entities = resp.json()["entities"]
        for ent in entities:
            start = ent["start_offset"]
            end = ent["end_offset"]
            extracted = FIR_TEXT[start:end]
            assert extracted == ent["value"], (
                f"Offset mismatch for {ent['entity_type']}: "
                f"text[{start}:{end}] = {extracted!r} but value = {ent['value']!r}"
            )


# ------------------------------------------------------------------
# 10. Empty Input Validation
# ------------------------------------------------------------------

class TestValidation:
    def test_empty_text_returns_error(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": ""})
        assert resp.status_code == 422  # Pydantic min_length=1

    def test_missing_text_returns_error(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={})
        assert resp.status_code == 422

    def test_whitespace_only_returns_400(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": "   "})
        assert resp.status_code == 400

    def test_resolve_empty_entities_returns_error(self, client: TestClient):
        resp = client.post("/api/v1/resolve", json={"entities": []})
        assert resp.status_code == 422  # min_length=1

    def test_resolve_missing_entities_returns_error(self, client: TestClient):
        resp = client.post("/api/v1/resolve", json={})
        assert resp.status_code == 422


# ------------------------------------------------------------------
# 11. Entity Resolution
# ------------------------------------------------------------------

class TestEntityResolution:
    def _make_entity(self, value: str, entity_type: str = "PERSON",
                     normalized: str | None = None) -> dict:
        return {
            "entity_id": f"test-{value}",
            "entity_type": entity_type,
            "value": value,
            "normalized_value": normalized or value.lower().strip(),
            "confidence": 0.9,
            "start_offset": 0,
            "end_offset": len(value),
            "source_field": "fir_text",
        }

    def test_fuzzy_person_resolution(self, client: TestClient):
        entities = [
            self._make_entity("Rajesh Kumar", normalized="rajesh kumar"),
            self._make_entity("RAJESH KUMAR", normalized="rajesh kumar"),
            self._make_entity("Rajesh K.", normalized="rajesh k."),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        # All three should be in the same group or at most two groups
        assert len(groups) >= 1
        # At least one group should have > 1 variant
        multi = [g for g in groups if len(g["variants"]) > 1]
        assert len(multi) >= 1

    def test_exact_phone_resolution(self, client: TestClient):
        entities = [
            self._make_entity("+91 98765 43210", "PHONE", "+919876543210"),
            self._make_entity("09876543210", "PHONE", "+919876543210"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        # Both should be in the same group (exact match on normalized)
        assert len(groups) == 1
        assert len(groups[0]["variants"]) == 2
        assert groups[0]["resolution_method"] == "exact_match"
        assert groups[0]["merge_confidence"] == 1.0

    def test_different_types_not_merged(self, client: TestClient):
        entities = [
            self._make_entity("Rajesh", "PERSON", "rajesh"),
            self._make_entity("Rajesh", "ORG", "rajesh"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        # Different entity types should never be merged
        assert len(groups) == 2


# ------------------------------------------------------------------
# 12. Duplicate Entity Handling
# ------------------------------------------------------------------

class TestDuplicateHandling:
    def test_exact_duplicate_phones_grouped(self, client: TestClient):
        text = "Call 9876543210 or 9876543210 for help."
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        phones = [e for e in entities if e["entity_type"] == "PHONE"]
        # Both occurrences should be extracted (different offsets)
        assert len(phones) == 2
        assert phones[0]["start_offset"] != phones[1]["start_offset"]


# ------------------------------------------------------------------
# 13. Confidence Bounds
# ------------------------------------------------------------------

class TestConfidenceBounds:
    def test_all_confidences_in_range(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        entities = resp.json()["entities"]
        assert len(entities) > 0
        for ent in entities:
            assert 0.0 <= ent["confidence"] <= 1.0, (
                f"Confidence {ent['confidence']} out of range for {ent}"
            )

    def test_resolution_confidences_in_range(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        entities = resp.json()["entities"]
        resp2 = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp2.json()["resolved_groups"]
        for g in groups:
            assert 0.0 <= g["merge_confidence"] <= 1.0


# ------------------------------------------------------------------
# 14. Multi-Entity Sentence
# ------------------------------------------------------------------

class TestMultiEntitySentence:
    def test_multiple_types_in_one_sentence(self, client: TestClient):
        text = (
            "Rajesh Kumar called from +91 98765 43210 while driving "
            "AP 39 AB 1234 near Hyderabad and paid via rajesh@oksbi."
        )
        resp = client.post("/api/v1/extract", json={"text": text})
        entities = resp.json()["entities"]
        types_found = {e["entity_type"] for e in entities}
        # Should find at least phone, vehicle, and UPI (regex-based)
        assert "PHONE" in types_found
        assert "VEHICLE" in types_found
        assert "UPI_ID" in types_found


# ------------------------------------------------------------------
# 15. Response Structure
# ------------------------------------------------------------------

class TestResponseStructure:
    def test_extract_response_shape(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["entities"], list)
        if data["entities"]:
            ent = data["entities"][0]
            assert "entity_id" in ent
            assert "entity_type" in ent
            assert "value" in ent
            assert "normalized_value" in ent
            assert "confidence" in ent
            assert "start_offset" in ent
            assert "end_offset" in ent
            assert "source_field" in ent

    def test_resolve_response_shape(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": FIR_TEXT})
        entities = resp.json()["entities"]
        resp2 = client.post("/api/v1/resolve", json={"entities": entities})
        data = resp2.json()
        assert data["status"] == "ok"
        assert isinstance(data["resolved_groups"], list)
        if data["resolved_groups"]:
            grp = data["resolved_groups"][0]
            assert "canonical_entity_id" in grp
            assert "canonical_value" in grp
            assert "entity_type" in grp
            assert "variants" in grp
            assert "merge_confidence" in grp
            assert "resolution_method" in grp

    def test_health_endpoint(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["service"] == "extraction"
        assert "spacy_model_loaded" in data


# ------------------------------------------------------------------
# 16. Source Field Propagation
# ------------------------------------------------------------------

class TestSourceField:
    def test_default_source_field(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={"text": "Call 9876543210."})
        entities = resp.json()["entities"]
        for ent in entities:
            assert ent["source_field"] == "fir_text"  # default

    def test_custom_source_field(self, client: TestClient):
        resp = client.post("/api/v1/extract", json={
            "text": "Call 9876543210.",
            "source_type": "call_record",
        })
        entities = resp.json()["entities"]
        for ent in entities:
            assert ent["source_field"] == "call_record"


# ------------------------------------------------------------------
# 17. DATE Excluded from Identity Resolution
# ------------------------------------------------------------------

class TestDateNotResolved:
    """DATE entities must NOT be grouped as identities by the resolver."""

    def _make_entity(self, value: str, entity_type: str = "DATE",
                     normalized: str | None = None) -> dict:
        return {
            "entity_id": f"test-{value}",
            "entity_type": entity_type,
            "value": value,
            "normalized_value": normalized or value.lower().strip(),
            "confidence": 0.7,
            "start_offset": 0,
            "end_offset": len(value),
            "source_field": "fir_text",
        }

    def test_dates_not_grouped(self, client: TestClient):
        """Different dates must not be merged as the same identity."""
        entities = [
            self._make_entity("15 January 2024", normalized="15 january 2024"),
            self._make_entity("15 January 2025", normalized="15 january 2025"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        # DATE should be excluded entirely from resolution groups
        date_groups = [g for g in groups if g["entity_type"] == "DATE"]
        assert len(date_groups) == 0

    def test_identical_dates_not_grouped(self, client: TestClient):
        """Even identical dates must not appear in resolution output."""
        entities = [
            self._make_entity("15 January 2024", normalized="15 january 2024"),
            self._make_entity("15 January 2024", normalized="15 january 2024"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        date_groups = [g for g in groups if g["entity_type"] == "DATE"]
        assert len(date_groups) == 0

    def test_date_with_other_types_only_others_resolved(self, client: TestClient):
        """When dates and persons are both submitted, only persons are resolved."""
        entities = [
            self._make_entity("15 January 2024", "DATE", "15 january 2024"),
            self._make_entity("Rajesh Kumar", "PERSON", "rajesh kumar"),
            self._make_entity("RAJESH KUMAR", "PERSON", "rajesh kumar"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        types_in_groups = {g["entity_type"] for g in groups}
        assert "DATE" not in types_in_groups
        assert "PERSON" in types_in_groups


# ------------------------------------------------------------------
# 18. Deterministic Canonical Entity IDs
# ------------------------------------------------------------------

class TestDeterministicCanonicalIds:
    """canonical_entity_id must be deterministic (SHA-256), not random."""

    def _make_entity(self, value: str, entity_type: str = "PERSON",
                     normalized: str | None = None) -> dict:
        return {
            "entity_id": f"test-{value}",
            "entity_type": entity_type,
            "value": value,
            "normalized_value": normalized or value.lower().strip(),
            "confidence": 0.9,
            "start_offset": 0,
            "end_offset": len(value),
            "source_field": "fir_text",
        }

    def test_same_person_same_canonical_id(self, client: TestClient):
        """Exact normalized variants must produce the same canonical_entity_id."""
        entities = [
            self._make_entity("Rajesh Kumar", normalized="rajesh kumar"),
            self._make_entity("RAJESH KUMAR", normalized="rajesh kumar"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        person_groups = [g for g in groups if g["entity_type"] == "PERSON"]
        assert len(person_groups) == 1
        canonical_id_1 = person_groups[0]["canonical_entity_id"]

        # Second independent call with the same input
        resp2 = client.post("/api/v1/resolve", json={"entities": entities})
        groups2 = resp2.json()["resolved_groups"]
        person_groups2 = [g for g in groups2 if g["entity_type"] == "PERSON"]
        assert len(person_groups2) == 1
        canonical_id_2 = person_groups2[0]["canonical_entity_id"]

        # Must be identical across calls
        assert canonical_id_1 == canonical_id_2

    def test_different_types_different_canonical_ids(self, client: TestClient):
        """Same value but different entity types must produce different IDs."""
        entities = [
            self._make_entity("1234567890", "PERSON", "1234567890"),
            self._make_entity("1234567890", "PHONE", "+911234567890"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        ids = [g["canonical_entity_id"] for g in groups]
        # Must have 2 groups with different IDs
        assert len(ids) == 2
        assert ids[0] != ids[1]

    def test_canonical_id_is_hex_string(self, client: TestClient):
        """canonical_entity_id must be a valid hex string (SHA-256)."""
        entities = [
            self._make_entity("Rajesh Kumar", normalized="rajesh kumar"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 1
        cid = groups[0]["canonical_entity_id"]
        # SHA-256 hex is 64 characters
        assert len(cid) == 64
        assert all(c in "0123456789abcdef" for c in cid)

    def test_phone_exact_resolution_deterministic(self, client: TestClient):
        """PHONE exact match must produce deterministic canonical ID."""
        entities = [
            self._make_entity("+91 98765 43210", "PHONE", "+919876543210"),
            self._make_entity("09876543210", "PHONE", "+919876543210"),
        ]
        resp1 = client.post("/api/v1/resolve", json={"entities": entities})
        resp2 = client.post("/api/v1/resolve", json={"entities": entities})
        g1 = resp1.json()["resolved_groups"]
        g2 = resp2.json()["resolved_groups"]
        assert len(g1) == 1 and len(g2) == 1
        assert g1[0]["canonical_entity_id"] == g2[0]["canonical_entity_id"]
        assert g1[0]["resolution_method"] == "exact_match"

    def test_vehicle_exact_resolution_deterministic(self, client: TestClient):
        """VEHICLE exact match must produce deterministic canonical ID."""
        entities = [
            self._make_entity("AP 39 AB 1234", "VEHICLE", "AP39AB1234"),
            self._make_entity("AP-39-AB-1234", "VEHICLE", "AP39AB1234"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 1
        assert groups[0]["resolution_method"] == "exact_match"
        assert len(groups[0]["canonical_entity_id"]) == 64  # SHA-256

    def test_upi_exact_resolution_deterministic(self, client: TestClient):
        """UPI_ID exact match must produce deterministic canonical ID."""
        entities = [
            self._make_entity("rajesh@oksbi", "UPI_ID", "rajesh@oksbi"),
            self._make_entity("RAJESH@OKSBI", "UPI_ID", "rajesh@oksbi"),
        ]
        resp = client.post("/api/v1/resolve", json={"entities": entities})
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 1
        assert groups[0]["resolution_method"] == "exact_match"
        assert len(groups[0]["canonical_entity_id"]) == 64
