import os
import secrets
from typing import Annotated

from fastapi import Header, HTTPException


def require_service_token(x_service_token: Annotated[str | None, Header()] = None):
    expected = os.environ.get("SERVICE_AUTH_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(503, "Ingestion service authentication is not configured")
    if not x_service_token or not secrets.compare_digest(x_service_token, expected):
        raise HTTPException(401, "Invalid service credentials")
