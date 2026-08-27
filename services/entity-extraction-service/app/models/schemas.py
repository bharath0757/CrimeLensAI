"""
CrimeLensAI — Extraction Service Schemas
==========================================
Pydantic models for the extraction service API.

These extend the shared contract (contracts/python/schemas.py) with
NLP-specific fields like ``normalized_value``.  The shared contract
is NOT modified — these are local extensions that remain a superset
of the shared ``ExtractedEntity`` and ``EntityResolutionGroup``.
"""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class EntityType(str, Enum):
    """Entity types supported by the extraction service."""
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    UPI_ID = "UPI_ID"
    LOCATION = "LOCATION"
    ORG = "ORG"
    DATE = "DATE"


class SourceType(str, Enum):
    """Types of source documents accepted for extraction."""
    FIR_TEXT = "fir_text"
    CALL_RECORD = "call_record"
    FINANCIAL_LOG = "financial_log"
    LOCATION_DATA = "location_data"


# ------------------------------------------------------------------
# Request Models
# ------------------------------------------------------------------

class ExtractionRequest(BaseModel):
    """Request body for ``POST /api/v1/extract``."""
    text: str = Field(
        ...,
        min_length=1,
        description="Raw text to extract entities from",
    )
    source_type: SourceType = Field(
        default=SourceType.FIR_TEXT,
        description="Type of source document",
    )
    case_id: Optional[str] = Field(
        default=None,
        description="Optional case ID for provenance tracking",
    )


class ResolutionRequest(BaseModel):
    """Request body for ``POST /api/v1/resolve``."""
    entities: list["ExtractedEntityResponse"] = Field(
        ...,
        min_length=1,
        description="List of extracted entities to resolve",
    )


# ------------------------------------------------------------------
# Response Models
# ------------------------------------------------------------------

class ExtractedEntityResponse(BaseModel):
    """
    A single extracted entity.

    Compatible with the shared ``ExtractedEntity`` contract, extended
    with ``normalized_value`` for downstream processing.
    """
    entity_id: str = Field(description="Unique identifier for this entity mention")
    entity_type: EntityType
    value: str = Field(description="Original extracted text")
    normalized_value: str = Field(description="Normalized form of the entity value")
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score")
    start_offset: int = Field(ge=0, description="Character start position in source text")
    end_offset: int = Field(ge=0, description="Character end position in source text")
    source_field: str = Field(description="Which input field the entity was found in")
    case_id: Optional[str] = Field(default=None, description="Associated case identifier")
    confirmed: Optional[bool] = Field(default=None, description="Review status (None = pending)")


class ExtractionResponse(BaseModel):
    """Response body for ``POST /api/v1/extract``."""
    status: str = "ok"
    entities: list[ExtractedEntityResponse] = []


class ResolvedGroup(BaseModel):
    """
    A group of entities resolved as the same real-world entity.

    Compatible with the shared ``EntityResolutionGroup`` contract,
    extended with ``canonical_entity_id`` and ``resolution_method``.
    """
    canonical_entity_id: str = Field(description="Stable identifier for the resolved entity")
    canonical_value: str = Field(description="Best representative value for the group")
    entity_type: EntityType
    variants: list[ExtractedEntityResponse] = Field(description="All mentions in this group")
    merge_confidence: float = Field(ge=0.0, le=1.0, description="Resolution confidence")
    resolution_method: str = Field(description="Method used: exact_match or fuzzy_match")


class ResolutionResponse(BaseModel):
    """Response body for ``POST /api/v1/resolve``."""
    status: str = "ok"
    resolved_groups: list[ResolvedGroup] = []


# Rebuild forward refs for ResolutionRequest which references ExtractedEntityResponse
ResolutionRequest.model_rebuild()
