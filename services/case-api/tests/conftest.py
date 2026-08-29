"""
Shared pytest fixtures for the Case API test suite.
"""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.schemas.entity import ExtractedEntity


@pytest.fixture(autouse=True)
def _reset_repos():
    """Reset in-memory repositories before each test for isolation."""
    from app.api import routes
    routes.case_repo._store.clear()
    routes.entity_repo._store.clear()
    yield
    routes.case_repo._store.clear()
    routes.entity_repo._store.clear()


@pytest.fixture(autouse=True)
def _mock_services():
    """
    Patch the module-level ai_service and graph_service in routes
    with mocks so tests are fully isolated from real services.
    """
    from app.integrations.ai_integration import MockAIService
    from app.integrations.graph_integration import MockGraphService
    from app.api import routes

    routes.ai_service = MockAIService()
    routes.graph_service = MockGraphService()
    yield


@pytest.fixture()
def client():
    """FastAPI TestClient (sync)."""
    from app.main import app
    return TestClient(app)


@pytest.fixture()
def sample_fir_payload():
    """Minimal case-creation payload with FIR text."""
    return {
        "title": "Robbery at Bank",
        "fir_text": (
            "On 15-03-2025, accused Rajesh Kumar (phone: +919876543210) "
            "robbed the State Bank of India branch in Mumbai. "
            "He fled in vehicle MH 12 AB 1234."
        ),
        "district": "Mumbai Suburban",
        "station": "Andheri",
    }


@pytest.fixture()
def mock_nlp_entities():
    """Fake NLP extraction response with entities."""
    return {
        "status": "ok",
        "entities": [
            {
                "entity_type": "PERSON",
                "value": "Rajesh Kumar",
                "confidence": 0.85,
                "start_offset": 27,
                "end_offset": 39,
                "source_field": "text",
            },
            {
                "entity_type": "PHONE",
                "value": "+919876543210",
                "confidence": 0.95,
                "start_offset": 48,
                "end_offset": 61,
                "source_field": "text",
            },
        ],
    }
