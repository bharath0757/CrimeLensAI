"""
CrimeLensAI — Extraction Service Schemas
==========================================
Pydantic models for the extraction service API.

These extend the shared contract (contracts/python/schemas.py) with
NLP-specific fields like ``normalized_value``.  The shared contract
is NOT modified — these are local extensions that remain a superset
of the shared ``ExtractedEntity`` and ``EntityResolutionGroup``.
"""

from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

# ------------------------------------------------------------------
# Enums
# ------------------------------------------------------------------

class EntityType(StrEnum):
    """Entity types supported by the extraction service."""
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    UPI_ID = "UPI_ID"
    LOCATION = "LOCATION"
    ORG = "ORG"
    DATE = "DATE"
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    PASSPORT = "PASSPORT"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    EMAIL = "EMAIL"
    IPC_SECTION = "IPC_SECTION"


class SourceType(StrEnum):
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
        max_length=500_000,
        description="Raw text to extract entities from",
    )
    source_type: SourceType = Field(
        default=SourceType.FIR_TEXT,
        description="Type of source document",
    )
    case_id: str | None = Field(
        default=None,
        description="Optional case ID for provenance tracking",
    )
    source_field: str | None = Field(
        default=None,
        description="Optional explicit source field retained for backwards compatibility",
    )

    @model_validator(mode="after")
    def normalize_source_field(self):
        if not self.source_field:
            self.source_field = self.source_type.value
        return self


class FirDocument(BaseModel):
    """Raw FIR narrative with provenance used by batch analysis."""
    case_id: str = Field(min_length=1, max_length=200)
    raw_text: str = Field(min_length=1, max_length=500_000)
    source_field: str = Field(default="fir_text", min_length=1, max_length=100)
    district: str | None = Field(default=None, max_length=200)
    fir_number: str | None = Field(default=None, max_length=200)


class BatchExtractionRequest(BaseModel):
    """Bounded collection of FIRs for one analysis run."""
    firs: list[FirDocument] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_case_ids(self):
        if any(not fir.raw_text.strip() for fir in self.firs):
            raise ValueError("FIR text must not be blank")
        if sum(len(fir.raw_text) for fir in self.firs) > 2_000_000:
            raise ValueError("Batch text must not exceed 2,000,000 characters")
        case_ids = [fir.case_id for fir in self.firs]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id values must be unique within a batch")
        return self


class ResolutionRequest(BaseModel):
    """Request body for ``POST /api/v1/resolve``."""
    entities: list["ExtractedEntityResponse"] = Field(
        ...,
        min_length=1,
        max_length=1_000,
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
    case_id: str | None = Field(default=None, description="Associated case identifier")
    confirmed: bool | None = Field(default=None, description="Review status (None = pending)")


class ExtractionResponse(BaseModel):
    """Response body for ``POST /api/v1/extract``."""
    status: str = "ok"
    entities: list[ExtractedEntityResponse] = Field(default_factory=list)
    model: str = "hybrid-regex-spacy"
    warnings: list[str] = Field(default_factory=list)


class FirExtractionResult(BaseModel):
    case_id: str
    district: str | None = None
    fir_number: str | None = None
    entities: list[ExtractedEntityResponse] = Field(default_factory=list)
    model: str = "hybrid-regex-spacy"
    warnings: list[str] = Field(default_factory=list)


class BatchExtractionResponse(BaseModel):
    cases_processed: int
    entities_extracted: int
    results: list[FirExtractionResult] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


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
    requires_review: bool = Field(
        default=True,
        description="Matching mentions is a reviewable lead, not proof of a shared identity",
    )


class ResolutionResponse(BaseModel):
    """Response body for ``POST /api/v1/resolve``."""
    status: str = "ok"
    resolved_groups: list[ResolvedGroup] = Field(default_factory=list)


# Rebuild forward refs for ResolutionRequest which references ExtractedEntityResponse
ResolutionRequest.model_rebuild()
