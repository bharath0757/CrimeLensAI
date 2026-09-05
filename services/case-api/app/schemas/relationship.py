from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.entity import EntityType


class RelationshipType(StrEnum):
    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    TRANSFERRED_FUNDS = "TRANSFERRED_FUNDS"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MEMBER_OF = "MEMBER_OF"
    LOCATED_AT = "LOCATED_AT"
    OWNER_OF = "OWNER_OF"
    ATTENDED_EVENT = "ATTENDED_EVENT"
    SUSPECT_IN = "SUSPECT_IN"
    OTHER = "OTHER"
    CALLED = "CALLED"
    TRANSFERRED_TO = "TRANSFERRED_TO"
    OWNS = "OWNS"
    INVOLVED_IN = "INVOLVED_IN"
    HAS_ACCOUNT = "HAS_ACCOUNT"
    REGISTERED_TO = "REGISTERED_TO"


class RelationshipBase(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class RelationshipCreate(RelationshipBase):
    source_document_id: str | None = None


class RelationshipUpdate(BaseModel):
    relationship_type: RelationshipType | None = None
    description: str | None = None
    properties: dict[str, Any] | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)


class RelationshipResponse(RelationshipBase):
    id: str
    case_id: str
    source_document_id: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RelationshipListResponse(BaseModel):
    total: int
    items: list[RelationshipResponse]


# AI Ingestion Contract Schemas
class ExtractedEntityIngest(BaseModel):
    name: str
    entity_type: EntityType
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractedRelationshipIngest(BaseModel):
    source_entity_name: str
    target_entity_name: str
    relationship_type: RelationshipType
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AIExtractionIngestRequest(BaseModel):
    document_id: str
    case_id: str
    entities: list[ExtractedEntityIngest] = Field(default_factory=list)
    relationships: list[ExtractedRelationshipIngest] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class AIExtractionIngestResponse(BaseModel):
    success: bool
    case_id: str
    document_id: str
    entities_created: int
    relationships_created: int
    message: str
