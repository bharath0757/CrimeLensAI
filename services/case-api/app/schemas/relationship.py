from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.entity import EntityCreate, EntityType


class RelationshipType(str, Enum):
    COMMUNICATED_WITH = "COMMUNICATED_WITH"
    TRANSFERRED_FUNDS = "TRANSFERRED_FUNDS"
    ASSOCIATED_WITH = "ASSOCIATED_WITH"
    MEMBER_OF = "MEMBER_OF"
    LOCATED_AT = "LOCATED_AT"
    OWNER_OF = "OWNER_OF"
    ATTENDED_EVENT = "ATTENDED_EVENT"
    SUSPECT_IN = "SUSPECT_IN"
    OTHER = "OTHER"


class RelationshipBase(BaseModel):
    source_entity_id: str
    target_entity_id: str
    relationship_type: RelationshipType
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class RelationshipCreate(RelationshipBase):
    source_document_id: Optional[str] = None


class RelationshipUpdate(BaseModel):
    relationship_type: Optional[RelationshipType] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class RelationshipResponse(RelationshipBase):
    id: str
    case_id: str
    source_document_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RelationshipListResponse(BaseModel):
    total: int
    items: List[RelationshipResponse]


# AI Ingestion Contract Schemas
class ExtractedEntityIngest(BaseModel):
    name: str
    entity_type: EntityType
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class ExtractedRelationshipIngest(BaseModel):
    source_entity_name: str
    target_entity_name: str
    relationship_type: RelationshipType
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class AIExtractionIngestRequest(BaseModel):
    document_id: str
    case_id: str
    entities: List[ExtractedEntityIngest] = Field(default_factory=list)
    relationships: List[ExtractedRelationshipIngest] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AIExtractionIngestResponse(BaseModel):
    success: bool
    case_id: str
    document_id: str
    entities_created: int
    relationships_created: int
    message: str
