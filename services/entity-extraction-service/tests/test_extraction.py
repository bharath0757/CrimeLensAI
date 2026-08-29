"""
Comprehensive test suite for the Entity Extraction Service.

Covers:
  - PERSON, PHONE, LOCATION, ORG, VEHICLE, UPI_ID extraction
  - Source offset correctness
  - Deduplication of overlapping spans
  - Confidence range (0.0–1.0)
  - Empty / whitespace input
  - Entity resolution: name variants merge
  - Entity resolution: unrelated names stay separate
  - Health endpoint
"""

import pytest

from app.extractors.nlp_pipeline import extract_entities
from app.extractors.resolver import resolve_entities


# ════════════════════════════════════════════════════════════
# Extraction tests
# ════════════════════════════════════════════════════════════


class TestPersonExtraction:
    """PERSON entities via spaCy NER."""

    def test_person_extracted(self, sample_fir_text):
        entities = extract_entities(sample_fir_text)
        persons = [e for e in entities if e.entity_type == "PERSON"]
        values = [p.value for p in persons]
        assert any("Rajesh" in v for v in values), (
            f"Expected a PERSON containing 'Rajesh', got {values}"
        )

    def test_person_offset(self):
        text = "The accused Rajesh Kumar was seen."
        entities = extract_entities(text)
        persons = [e for e in entities if e.entity_type == "PERSON"]
        for p in persons:
            assert text[p.start_offset : p.end_offset] == p.value


class TestPhoneExtraction:
    """PHONE entities via regex."""

    def test_phone_with_plus91(self):
        text = "Contact the witness at +919876543210 for details."
        entities = extract_entities(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) >= 1
        assert any("+919876543210" in p.value for p in phones)

    def test_phone_ten_digit(self):
        text = "His number is 9876543210."
        entities = extract_entities(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) >= 1

    def test_phone_with_zero_prefix(self):
        text = "Call 09876543210 for info."
        entities = extract_entities(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        assert len(phones) >= 1

    def test_phone_offset(self):
        text = "Call +919876543210 now."
        entities = extract_entities(text)
        phones = [e for e in entities if e.entity_type == "PHONE"]
        for p in phones:
            assert text[p.start_offset : p.end_offset] == p.value


class TestLocationExtraction:
    """LOCATION entities via spaCy NER (GPE/LOC/FAC → LOCATION)."""

    def test_location_extracted(self):
        text = "The incident occurred in Mumbai near the railway station."
        entities = extract_entities(text)
        locations = [e for e in entities if e.entity_type == "LOCATION"]
        values = [loc.value for loc in locations]
        assert any("Mumbai" in v for v in values), (
            f"Expected a LOCATION containing 'Mumbai', got {values}"
        )

    def test_location_offset(self):
        text = "He was found in Delhi."
        entities = extract_entities(text)
        locations = [e for e in entities if e.entity_type == "LOCATION"]
        for loc in locations:
            assert text[loc.start_offset : loc.end_offset] == loc.value


class TestOrgExtraction:
    """ORG entities via spaCy NER."""

    def test_org_extracted(self):
        text = "The complaint was filed against State Bank of India for fraud."
        entities = extract_entities(text)
        orgs = [e for e in entities if e.entity_type == "ORG"]
        assert len(orgs) >= 1, "Expected at least one ORG entity"

    def test_org_offset(self):
        text = "He works at Tata Consultancy Services in Pune."
        entities = extract_entities(text)
        orgs = [e for e in entities if e.entity_type == "ORG"]
        for o in orgs:
            assert text[o.start_offset : o.end_offset] == o.value


class TestVehicleExtraction:
    """VEHICLE registration numbers via regex."""

    def test_vehicle_extracted(self):
        text = "The suspect fled in a vehicle bearing registration MH 12 AB 1234."
        entities = extract_entities(text)
        vehicles = [e for e in entities if e.entity_type == "VEHICLE"]
        assert len(vehicles) >= 1

    def test_vehicle_offset(self):
        text = "Vehicle number KA 01 MN 5678 was spotted."
        entities = extract_entities(text)
        vehicles = [e for e in entities if e.entity_type == "VEHICLE"]
        for v in vehicles:
            # The raw text at the offset should match the stored value
            assert text[v.start_offset : v.end_offset] == v.value

    def test_vehicle_no_spaces(self):
        text = "Plate: MH12AB1234 seen."
        entities = extract_entities(text)
        vehicles = [e for e in entities if e.entity_type == "VEHICLE"]
        assert len(vehicles) >= 1


class TestUpiExtraction:
    """UPI_ID entities via regex."""

    def test_upi_extracted(self):
        text = "The payment was sent to suspect.user@upi via PhonePe."
        entities = extract_entities(text)
        upis = [e for e in entities if e.entity_type == "UPI_ID"]
        assert len(upis) >= 1
        assert upis[0].value == "suspect.user@upi"

    def test_upi_paytm(self):
        text = "UPI ID: criminal123@paytm was used."
        entities = extract_entities(text)
        upis = [e for e in entities if e.entity_type == "UPI_ID"]
        assert len(upis) >= 1
        assert "criminal123@paytm" in upis[0].value

    def test_upi_offset(self):
        text = "UPI ID: criminal123@paytm was used."
        entities = extract_entities(text)
        upis = [e for e in entities if e.entity_type == "UPI_ID"]
        for u in upis:
            assert text[u.start_offset : u.end_offset] == u.value


# ════════════════════════════════════════════════════════════
# Cross-cutting extraction tests
# ════════════════════════════════════════════════════════════


class TestSourceOffsets:
    """Offsets must index into the original text for every entity type."""

    def test_all_offsets_valid(self, sample_fir_text):
        entities = extract_entities(sample_fir_text)
        for e in entities:
            raw = sample_fir_text[e.start_offset : e.end_offset]
            assert raw == e.value, (
                f"Offset mismatch for {e.entity_type} entity: "
                f"text[{e.start_offset}:{e.end_offset}] = {raw!r}, "
                f"value = {e.value!r}"
            )


class TestDeduplication:
    """Overlapping spans should not produce duplicate entities."""

    def test_no_duplicate_spans(self, sample_fir_text):
        entities = extract_entities(sample_fir_text)
        for i, e1 in enumerate(entities):
            for j, e2 in enumerate(entities):
                if i >= j:
                    continue
                overlap = max(
                    0,
                    min(e1.end_offset, e2.end_offset)
                    - max(e1.start_offset, e2.start_offset),
                )
                shorter = min(
                    e1.end_offset - e1.start_offset,
                    e2.end_offset - e2.start_offset,
                )
                if shorter > 0:
                    ratio = overlap / shorter
                    assert ratio < 0.5, (
                        f"Entities overlap ≥50%: [{e1.entity_type}]{e1.value!r} "
                        f"and [{e2.entity_type}]{e2.value!r}"
                    )


class TestConfidenceRange:
    """Every entity's confidence must be between 0.0 and 1.0."""

    def test_all_confidence_in_range(self, sample_fir_text):
        entities = extract_entities(sample_fir_text)
        assert len(entities) > 0, "Expected at least one entity"
        for e in entities:
            assert 0.0 <= e.confidence <= 1.0, (
                f"Confidence out of range for {e.entity_type}: {e.confidence}"
            )


class TestEmptyInput:
    """Edge cases: empty, whitespace, and None-like input."""

    def test_empty_string(self):
        assert extract_entities("") == []

    def test_whitespace_only(self):
        assert extract_entities("   \n\t  ") == []

    def test_no_entities_text(self):
        # Text with no recognisable entities
        entities = extract_entities("the quick brown fox jumps over the lazy dog")
        # Should not crash; may return empty or just common-noun false positives
        for e in entities:
            assert 0.0 <= e.confidence <= 1.0


# ════════════════════════════════════════════════════════════
# API-level extraction tests
# ════════════════════════════════════════════════════════════


class TestExtractEndpoint:
    """POST /api/v1/extract via TestClient."""

    def test_extract_returns_200(self, client, sample_fir_text):
        resp = client.post("/api/v1/extract", json={
            "text": sample_fir_text,
            "source_type": "fir_text",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert isinstance(data["entities"], list)
        assert len(data["entities"]) > 0

    def test_extract_empty_text(self, client):
        resp = client.post("/api/v1/extract", json={"text": ""})
        assert resp.status_code == 200
        assert resp.json()["entities"] == []

    def test_extract_missing_text(self, client):
        resp = client.post("/api/v1/extract", json={})
        assert resp.status_code == 422  # Pydantic validation error

    def test_entity_shape(self, client, sample_fir_text):
        resp = client.post("/api/v1/extract", json={"text": sample_fir_text})
        data = resp.json()
        required_keys = {
            "entity_type", "value", "confidence",
            "start_offset", "end_offset", "source_field",
        }
        for ent in data["entities"]:
            assert required_keys.issubset(ent.keys()), (
                f"Entity missing keys: {required_keys - ent.keys()}"
            )


# ════════════════════════════════════════════════════════════
# Entity Resolution tests
# ════════════════════════════════════════════════════════════


class TestEntityResolution:
    """POST /api/v1/resolve — fuzzy grouping."""

    def _make_entity(self, value, etype="PERSON", start=0):
        return {
            "entity_type": etype,
            "value": value,
            "confidence": 0.85,
            "start_offset": start,
            "end_offset": start + len(value),
            "source_field": "text",
        }

    def test_name_variants_merge(self, client):
        resp = client.post("/api/v1/resolve", json={
            "entities": [
                self._make_entity("Rajesh Kumar", start=0),
                self._make_entity("R. Kumar", start=50),
            ],
        })
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 1, (
            f"Expected 1 group for name variants, got {len(groups)}: {groups}"
        )
        assert groups[0]["canonical_value"] == "Rajesh Kumar"
        assert len(groups[0]["variants"]) == 2

    def test_abbreviated_first_name(self, client):
        resp = client.post("/api/v1/resolve", json={
            "entities": [
                self._make_entity("Rajesh Kumar", start=0),
                self._make_entity("Rajesh K.", start=50),
            ],
        })
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 1

    def test_unrelated_names_not_merged(self, client):
        resp = client.post("/api/v1/resolve", json={
            "entities": [
                self._make_entity("Rajesh Kumar", start=0),
                self._make_entity("Amit Sharma", start=50),
            ],
        })
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        assert len(groups) == 2, (
            f"Expected 2 groups for unrelated names, got {len(groups)}: {groups}"
        )

    def test_phone_variants_exact(self, client):
        resp = client.post("/api/v1/resolve", json={
            "entities": [
                self._make_entity("+919876543210", etype="PHONE", start=0),
                self._make_entity("09876543210", etype="PHONE", start=50),
            ],
        })
        assert resp.status_code == 200
        groups = resp.json()["resolved_groups"]
        # Should merge: both normalise to 9876543210
        assert len(groups) == 1

    def test_empty_resolution(self, client):
        resp = client.post("/api/v1/resolve", json={"entities": []})
        assert resp.status_code == 200
        assert resp.json()["resolved_groups"] == []

    def test_resolution_group_shape(self, client):
        resp = client.post("/api/v1/resolve", json={
            "entities": [self._make_entity("Rajesh Kumar")],
        })
        data = resp.json()
        assert data["status"] == "ok"
        group = data["resolved_groups"][0]
        assert "canonical_value" in group
        assert "entity_type" in group
        assert "variants" in group
        assert "merge_confidence" in group
        assert 0.0 <= group["merge_confidence"] <= 1.0


# ════════════════════════════════════════════════════════════
# Health endpoint
# ════════════════════════════════════════════════════════════


class TestHealth:
    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
