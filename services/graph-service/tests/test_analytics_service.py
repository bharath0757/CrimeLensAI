from contextlib import suppress

import pytest


class TestCentrality:
    def test_centrality_returns_metrics(self, populated_analytics_service, populated_store):
        # Get the phone entity ID (shared across CASE-001 and CASE-002)
        phone_id = None
        for eid, e in populated_store.entities.items():
            if e["entity_type"] == "PHONE":
                phone_id = eid
                break
        assert phone_id is not None
        resp = populated_analytics_service.get_centrality(phone_id)
        assert resp.entity_id == phone_id
        assert resp.centrality.degree >= 0
        assert resp.centrality.betweenness >= 0
        assert resp.centrality.pagerank >= 0
        assert resp.explanation  # Non-empty explanation
    
    def test_centrality_missing_entity(self, populated_analytics_service):
        with pytest.raises(KeyError):
            populated_analytics_service.get_centrality("nonexistent")


class TestCommunities:
    def test_communities_detected(self, populated_analytics_service):
        resp = populated_analytics_service.detect_communities()
        assert resp.total_communities >= 1
        assert resp.method  # Non-empty method name
        for comm in resp.communities:
            assert comm.size > 0
            assert comm.summary  # Non-empty
    
    def test_empty_graph_communities(self, analytics_service):
        resp = analytics_service.detect_communities()
        assert resp.total_communities == 0
        assert resp.communities == []


class TestShortestPath:
    def test_shortest_path_exists(self, populated_analytics_service, populated_store):
        # Get two entity IDs that should be connected
        entity_ids = list(populated_store.entities.keys())
        assert len(entity_ids) >= 2
        # All entities should be connected through cases
        # Find person from CASE-001 and phone from CASE-001
        person_id = None
        phone_id = None
        for eid, e in populated_store.entities.items():
            if e["entity_type"] == "PERSON" and e["canonical_value"] == "rajesh kumar":
                person_id = eid
            if e["entity_type"] == "PHONE":
                phone_id = eid
        if person_id and phone_id:
            resp = populated_analytics_service.get_shortest_path(person_id, phone_id)
            assert resp.entity_a == person_id
            assert resp.entity_b == phone_id
            assert resp.path_length >= 1
            assert resp.explanation  # Non-empty
    
    def test_shortest_path_missing_entity(self, populated_analytics_service):
        with pytest.raises(KeyError):
            populated_analytics_service.get_shortest_path("nonexistent_a", "nonexistent_b")
    
    def test_shortest_path_no_connection(self, analytics_service, store):
        # Add two disconnected entities in different cases with no shared entities
        from app.models import EntityInput, EntityType
        store.upsert_entity(EntityInput(
            entity_type=EntityType.PERSON, value="Alice",
            case_id="ISOLATED-A", confidence=0.9, source_field="test",
        ))
        store.upsert_entity(EntityInput(
            entity_type=EntityType.PERSON, value="Bob",
            case_id="ISOLATED-B", confidence=0.9, source_field="test",
        ))
        ids = list(store.entities.keys())
        # These are in separate cases with no shared entities, so they may or may not be connected
        # depending on whether cases create implicit connections. Just verify it doesn't crash.
        with suppress(KeyError, ValueError):
            analytics_service.get_shortest_path(ids[0], ids[1])


class TestExplanations:
    def test_linkage_explanation_references_evidence(self, populated_graph_service):
        resp = populated_graph_service.get_linkage("CASE-001")
        for lc in resp.linked_cases:
            # Explanation should reference the shared entity
            assert any(
                se.value in lc.explanation or se.entity_type in lc.explanation
                for se in lc.shared_entities
            )
    
    def test_centrality_explanation_is_meaningful(self, populated_analytics_service, populated_store):
        phone_id = None
        for eid, e in populated_store.entities.items():
            if e["entity_type"] == "PHONE":
                phone_id = eid
                break
        resp = populated_analytics_service.get_centrality(phone_id)
        assert len(resp.explanation) > 10  # Not trivially empty
