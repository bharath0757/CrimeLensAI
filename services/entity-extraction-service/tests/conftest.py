"""
Shared test fixtures for the extraction service.
"""

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    """FastAPI test client scoped to the test module."""
    token = "extraction-test-service-token-26189"
    with (
        patch.dict(os.environ, {"SERVICE_AUTH_TOKEN": token}),
        TestClient(app, headers={"X-Service-Token": token}) as c,
    ):
        yield c
