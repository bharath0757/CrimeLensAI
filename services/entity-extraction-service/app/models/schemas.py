"""
CrimeLensAI — Extraction Service: Local Pydantic Models
=========================================================
Mirrors the shared contract in contracts/python/schemas.py for the
entity-extraction fields only.  Kept local so the service has no
cross-package import dependency at runtime.

Matches contracts/openapi/extraction.yaml exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ───────────────────────────────────────────────────

class EntityType(str, Enum):
    """Entity types supported by the extraction pipeline."""
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    UPI_ID = "UPI_ID"
    LOCATION = "LOCATION"
    ORG = "ORG"


# ── Extraction ──────────────────────────────────────────────

class ExtractionRequest(BaseModel):
    """POST /api/v1/extract request body."""
    text: str
    source_type: str = "fir_text"


class ExtractedEntity(BaseModel):
    """A single extracted entity with offsets into the source text."""
    id: Optional[str] = None
    entity_type: EntityType
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    source_field: str = "text"
    case_id: Optional[str] = None
    confirmed: Optional[bool] = None


class ExtractionResponse(BaseModel):
    """POST /api/v1/extract response body."""
    status: str = "ok"
    entities: List[ExtractedEntity] = []


# ── Resolution ──────────────────────────────────────────────

class ResolutionRequest(BaseModel):
    """POST /api/v1/resolve request body."""
    entities: List[ExtractedEntity]


class EntityResolutionGroup(BaseModel):
    """A group of entities resolved as referring to the same real-world thing."""
    canonical_value: str
    entity_type: EntityType
    variants: List[ExtractedEntity]
    merge_confidence: float = Field(ge=0.0, le=1.0)


class ResolutionResponse(BaseModel):
    """POST /api/v1/resolve response body."""
    status: str = "ok"
    resolved_groups: List[EntityResolutionGroup] = []
