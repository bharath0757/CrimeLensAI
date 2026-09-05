from unittest.mock import MagicMock

import pytest
from app.models import EntityInput, EntityType
from app.services.analytics_service import AnalyticsService
from app.services.graph_service import GraphService
from app.store import InMemoryGraphStore


@pytest.fixture
def store():
    return InMemoryGraphStore()


@pytest.fixture
def graph_service(store):
    return GraphService(store)


@pytest.fixture
def analytics_service(store):
    return AnalyticsService(store)


@pytest.fixture
def mock_neo4j_driver():
    driver = MagicMock()
    driver.verify_connectivity.return_value = None
    session = MagicMock()
    driver.session.return_value.__enter__ = MagicMock(return_value=session)
    driver.session.return_value.__exit__ = MagicMock(return_value=False)
    return driver, session


def _add_entity(store, case_id, entity_type, value, confidence=0.95):
    """Helper to add an entity to the store."""
    return store.upsert_entity(EntityInput(
        entity_type=entity_type,
        value=value,
        confidence=confidence,
        case_id=case_id,
        source_field="fir_text",
        start_offset=10,
        end_offset=20,
    ))


@pytest.fixture
def populated_store(store):
    """Store with synthetic CASE-001, CASE-002, CASE-003 data."""
    # CASE-001: Rajesh Kumar, Phone +919876543210, Vehicle AP39AB1234, UPI rajesh@oksbi
    _add_entity(store, "CASE-001", EntityType.PERSON, "Rajesh Kumar")
    _add_entity(store, "CASE-001", EntityType.PHONE, "+919876543210")
    _add_entity(store, "CASE-001", EntityType.VEHICLE, "AP39AB1234")
    _add_entity(store, "CASE-001", EntityType.UPI_ID, "rajesh@oksbi")
    
    # CASE-002: Ramesh Kumar, Phone +919876543210 (SHARED!), Vehicle KA01MG1234
    _add_entity(store, "CASE-002", EntityType.PERSON, "Ramesh Kumar")
    _add_entity(store, "CASE-002", EntityType.PHONE, "+919876543210")
    _add_entity(store, "CASE-002", EntityType.VEHICLE, "KA01MG1234")
    
    # CASE-003: Suresh Reddy, Vehicle AP39AB1234 (SHARED with CASE-001!)
    _add_entity(store, "CASE-003", EntityType.PERSON, "Suresh Reddy")
    _add_entity(store, "CASE-003", EntityType.VEHICLE, "AP39AB1234")
    
    return store


@pytest.fixture
def populated_graph_service(populated_store):
    return GraphService(populated_store)


@pytest.fixture
def populated_analytics_service(populated_store):
    return AnalyticsService(populated_store)
