import pytest
from app.models.schemas import (
    EntityType,
    EntityUpsertRequest,
    RelationshipCreateRequest,
)
from pydantic import ValidationError


class TestEntityUpsertRequest:
    def test_valid_entity(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PERSON,
            value="Rajesh Kumar", confidence=0.85,
        )
        assert req.case_id == "CASE-001"
        assert req.entity_type == EntityType.PERSON
    
    def test_accepts_entity_id_field(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_id="abc123",
            entity_type=EntityType.PHONE, value="+919876543210",
        )
        assert req.entity_id == "abc123"
    
    def test_accepts_id_alias(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", id="abc123",
            entity_type=EntityType.PHONE, value="+919876543210",
        )
        assert req.entity_id == "abc123"
    
    def test_accepts_normalized_value(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PERSON,
            value="Rajesh Kumar", normalized_value="rajesh kumar",
        )
        assert req.normalized_value == "rajesh kumar"
    
    def test_accepts_canonical_value_alias(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PERSON,
            value="Rajesh Kumar", canonical_value="rajesh kumar",
        )
        assert req.normalized_value == "rajesh kumar"
    
    def test_rejects_empty_case_id(self):
        with pytest.raises(ValidationError):
            EntityUpsertRequest(
                case_id="", entity_type=EntityType.PERSON, value="X",
            )
    
    def test_rejects_empty_value(self):
        with pytest.raises(ValidationError):
            EntityUpsertRequest(
                case_id="CASE-001", entity_type=EntityType.PERSON, value="",
            )
    
    def test_rejects_invalid_entity_type(self):
        with pytest.raises(ValidationError):
            EntityUpsertRequest(
                case_id="CASE-001", entity_type="INVALID_TYPE", value="X",
            )
    
    def test_rejects_confidence_above_1(self):
        with pytest.raises(ValidationError):
            EntityUpsertRequest(
                case_id="CASE-001", entity_type=EntityType.PERSON,
                value="X", confidence=1.5,
            )
    
    def test_rejects_confidence_below_0(self):
        with pytest.raises(ValidationError):
            EntityUpsertRequest(
                case_id="CASE-001", entity_type=EntityType.PERSON,
                value="X", confidence=-0.1,
            )
    
    def test_default_confidence_is_1(self):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PERSON, value="X",
        )
        assert req.confidence == 1.0
    
    def test_all_entity_types_valid(self):
        for et in EntityType:
            req = EntityUpsertRequest(
                case_id="CASE-001", entity_type=et, value="test",
            )
            assert req.entity_type == et


class TestRelationshipCreateRequest:
    def test_valid_relationship(self):
        req = RelationshipCreateRequest(
            source_entity_id="a", target_entity_id="b",
            relationship_type="USES", source_case_id="CASE-001",
            confidence=0.9, why_linked="Evidence from FIR.",
        )
        assert req.relationship_type == "USES"
    
    def test_relationship_type_uppercased(self):
        req = RelationshipCreateRequest(
            source_entity_id="a", target_entity_id="b",
            relationship_type="uses", source_case_id="CASE-001",
            confidence=0.9, why_linked="Evidence.",
        )
        assert req.relationship_type == "USES"
    
    def test_rejects_invalid_relationship_type(self):
        with pytest.raises(ValidationError):
            RelationshipCreateRequest(
                source_entity_id="a", target_entity_id="b",
                relationship_type="INVALID_TYPE", source_case_id="CASE-001",
                confidence=0.9, why_linked="Evidence.",
            )
    
    def test_rejects_empty_source_entity_id(self):
        with pytest.raises(ValidationError):
            RelationshipCreateRequest(
                source_entity_id="", target_entity_id="b",
                relationship_type="USES", source_case_id="CASE-001",
                confidence=0.9, why_linked="Evidence.",
            )
    
    def test_rejects_empty_why_linked(self):
        with pytest.raises(ValidationError):
            RelationshipCreateRequest(
                source_entity_id="a", target_entity_id="b",
                relationship_type="USES", source_case_id="CASE-001",
                confidence=0.9, why_linked="",
            )
    
    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            RelationshipCreateRequest(
                source_entity_id="a", target_entity_id="b",
                relationship_type="USES", source_case_id="CASE-001",
                confidence=1.5, why_linked="X",
            )
