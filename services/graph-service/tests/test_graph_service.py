import pytest
from app.models.schemas import EntityUpsertRequest, EntityType, RelationshipCreateRequest
from app.services.graph_service import GraphService
from tests.conftest import _add_entity


class TestEntityUpsert:
    def test_create_new_entity(self, graph_service, store):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PERSON,
            value="Rajesh Kumar", confidence=0.85,
        )
        resp = graph_service.upsert_entity(req)
        assert resp.status == "created"
        assert resp.created is True
        assert resp.entity_type == "PERSON"
        assert "CASE-001" in resp.case_ids
    
    def test_idempotent_upsert(self, graph_service, store):
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PHONE,
            value="+919876543210", confidence=0.99,
        )
        r1 = graph_service.upsert_entity(req)
        r2 = graph_service.upsert_entity(req)
        assert r1.entity_id == r2.entity_id
        # Second call should say exists
        assert r2.status == "exists"
    
    def test_same_entity_different_case(self, graph_service, store):
        req1 = EntityUpsertRequest(
            case_id="CASE-001", entity_type=EntityType.PHONE,
            value="+919876543210",
        )
        req2 = EntityUpsertRequest(
            case_id="CASE-002", entity_type=EntityType.PHONE,
            value="9876543210",  # Different format, same canonical
        )
        r1 = graph_service.upsert_entity(req1)
        r2 = graph_service.upsert_entity(req2)
        assert r1.entity_id == r2.entity_id
        assert set(r2.case_ids) == {"CASE-001", "CASE-002"}
    
    def test_nlp_handoff_format(self, graph_service):
        # NLP produces entity_id and normalized_value
        req = EntityUpsertRequest(
            case_id="CASE-001", entity_id="cfd8eda1-test",
            entity_type=EntityType.PERSON, value="Rajesh Kumar",
            normalized_value="rajesh kumar", confidence=0.70,
        )
        resp = graph_service.upsert_entity(req)
        assert resp.entity_id is not None
        assert resp.canonical_value == "rajesh kumar"


class TestRelationshipCreate:
    def test_create_relationship(self, graph_service, store):
        # Add entities first
        _add_entity(store, "CASE-001", EntityType.PERSON, "Rajesh Kumar")
        _add_entity(store, "CASE-001", EntityType.PHONE, "+919876543210")
        person_id = list(store.entities.keys())[0]
        phone_id = list(store.entities.keys())[1]
        
        req = RelationshipCreateRequest(
            source_entity_id=person_id, target_entity_id=phone_id,
            relationship_type="USES", source_case_id="CASE-001",
            confidence=0.92, why_linked="Phone found in FIR.",
        )
        resp = graph_service.create_relationship(req)
        assert resp.status == "created"
        assert resp.relationship_type == "USES"
    
    def test_reject_missing_source_entity(self, graph_service, store):
        _add_entity(store, "CASE-001", EntityType.PHONE, "+919876543210")
        phone_id = list(store.entities.keys())[0]
        
        req = RelationshipCreateRequest(
            source_entity_id="nonexistent", target_entity_id=phone_id,
            relationship_type="USES", source_case_id="CASE-001",
            confidence=0.9, why_linked="Test.",
        )
        with pytest.raises(KeyError):
            graph_service.create_relationship(req)


class TestLinkage:
    def test_cross_case_linkage(self, populated_graph_service):
        resp = populated_graph_service.get_linkage("CASE-001")
        assert resp.case_id == "CASE-001"
        linked_case_ids = {lc.case_id for lc in resp.linked_cases}
        assert "CASE-002" in linked_case_ids  # shared PHONE
        assert "CASE-003" in linked_case_ids  # shared VEHICLE
    
    def test_linkage_has_explanation(self, populated_graph_service):
        resp = populated_graph_service.get_linkage("CASE-001")
        for lc in resp.linked_cases:
            assert lc.explanation  # Non-empty
            assert len(lc.shared_entities) > 0
    
    def test_linkage_nonexistent_case(self, populated_graph_service):
        resp = populated_graph_service.get_linkage("CASE-999")
        assert resp.case_id == "CASE-999"
        assert resp.linked_cases == []
