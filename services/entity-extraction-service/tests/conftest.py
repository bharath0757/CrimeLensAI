"""
Shared test fixtures for the extraction service.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """FastAPI test client scoped to the test module."""
    with TestClient(app) as c:
        yield c
