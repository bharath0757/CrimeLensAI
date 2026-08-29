"""
Shared pytest fixtures for the Extraction Service test suite.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture()
def client():
    """FastAPI test client."""
    return TestClient(app)


@pytest.fixture()
def sample_fir_text():
    """Realistic FIR text containing all supported entity types."""
    return (
        "On 15-03-2025, the complainant Rajesh Kumar (phone: +919876543210) "
        "reported that his vehicle MH 12 AB 1234 was stolen from Mumbai. "
        "He received a ransom demand via UPI ID criminal123@paytm. "
        "The suspect Amit Sharma was seen near the State Bank of India branch "
        "in Delhi. Inspector Sharma of Mumbai Police filed the report."
    )
