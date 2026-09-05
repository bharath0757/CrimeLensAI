"""A failed durable write must not become a successful in-memory graph result."""

from unittest.mock import MagicMock

import pytest
from app.models import EntityInput, RelationshipInput
from app.store import InMemoryGraphStore, Neo4jGraphStore


def phone(case_id="case-a", source="document-a", offset=0):
    return EntityInput(entity_type="PHONE", value="9000990189", case_id=case_id,
                       source_field=source, start_offset=offset, end_offset=offset + 10)


def test_uninitialized_neo4j_cannot_acknowledge_an_entity():
    store = Neo4jGraphStore()
    with pytest.raises(RuntimeError, match="not ready"):
        store.upsert_entity(phone())
    assert not store.entities
    assert not store.case_entities


def test_failed_entity_update_preserves_last_committed_occurrences():
    store = Neo4jGraphStore()
    store.repo = MagicMock()
    entity = store.upsert_entity(phone())["entity"]
    store.repo.upsert_entity.side_effect = RuntimeError("Database unavailable")
    with pytest.raises(RuntimeError):
        store.upsert_entity(phone("case-b", "document-b", 30))
    assert len(store.entities[entity["id"]]["occurrences"]) == 1
    assert "case-b" not in store.case_entities
    assert not store.alerts


def test_failed_relationship_is_not_visible_to_analytics():
    store = InMemoryGraphStore()
    first = store.upsert_entity(phone())["entity"]["id"]
    second = store.upsert_entity(EntityInput(entity_type="PHONE", value="9000990190", case_id="case-a"))["entity"]["id"]
    store._persist_relationship = MagicMock(side_effect=RuntimeError("Write rejected"))
    with pytest.raises(RuntimeError):
        store.create_relationship(RelationshipInput(source_entity_id=first, target_entity_id=second,
                                                    relationship_type="CALLED", source_case_id="case-a",
                                                    confidence=.95, why_linked="Synthetic call record"))
    assert not store.relationships


def test_failed_acknowledgement_keeps_alert_unread():
    store = InMemoryGraphStore()
    store.upsert_entity(phone())
    store.upsert_entity(phone("case-b", "document-b"))
    alert_id = next(iter(store.alerts))
    assert store.alerts[alert_id]["status"] == "NEW"
    store._persist_alert = MagicMock(side_effect=RuntimeError("Write rejected"))
    with pytest.raises(RuntimeError):
        store.acknowledge_alert(alert_id)
    assert store.alerts[alert_id]["status"] == "NEW"


def test_repository_persists_exact_money_as_integer_minor_units():
    from app.repositories.graph_repository import GraphRepository

    driver = MagicMock()
    session = driver.session.return_value.__enter__.return_value
    transaction = MagicMock()
    session.execute_write.side_effect = lambda operation: operation(transaction)
    GraphRepository(driver).create_relationship("a", "b", "TRANSFERRED_TO", "case-1", 1.0, "Synthetic transaction",
        "relationship-1", "TX-1", {"amount": "999999999999.99", "currency": "INR", "timestamp": "2026-09-04T12:00:00Z", "sources": []})
    params = transaction.run.call_args.kwargs
    assert params["amount_minor"] == 99_999_999_999_999
    assert params["currency"] == "INR"
    assert '"999999999999.99"' in params["evidence_json"]
