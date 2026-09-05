"""Service-to-service authentication for NLP operations."""

import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException


def require_service_token(x_service_token: Annotated[str | None, Header()] = None) -> None:
    expected = os.getenv("SERVICE_AUTH_TOKEN", "")
    if len(expected.encode()) < 32:
        raise HTTPException(503, "Extraction service authentication is not configured")
    if not x_service_token or not secrets.compare_digest(x_service_token, expected):
        raise HTTPException(401, "Invalid service credentials")
