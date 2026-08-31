from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    PHONE_NUMBER = "PHONE_NUMBER"
    EMAIL = "EMAIL"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    VEHICLE = "VEHICLE"
    OTHER = "OTHER"


class EntityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    entity_type: EntityType
    description: Optional[str] = None
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class EntityCreate(EntityBase):
    source_document_id: Optional[str] = None


class EntityUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    entity_type: Optional[EntityType] = None
    description: Optional[str] = None
    properties: Optional[Dict[str, Any]] = None
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0)


class EntityResponse(EntityBase):
    id: str
    case_id: str
    source_document_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class EntityListResponse(BaseModel):
    total: int
    items: List[EntityResponse]
class ExtractedEntity(BaseModel):
    id: Optional[str] = None
    entity_type: str
    value: str
    confidence: float
    start_offset: int
    end_offset: int
    source_field: str = "text"
    case_id: Optional[str] = None
    confirmed: Optional[bool] = None
