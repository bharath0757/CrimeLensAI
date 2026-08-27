"""Typed graph-service API models."""

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class EntityType(str, Enum):
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    UPI_ID = "UPI_ID"
    LOCATION = "LOCATION"
    ORG = "ORG"


class EntityInput(BaseModel):
    id: Optional[str] = None
    entity_type: EntityType
    value: str = Field(min_length=1)
    canonical_value: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    case_id: str = Field(min_length=1)
    source_field: str = "unknown"
    start_offset: Optional[int] = Field(default=None, ge=0)
    end_offset: Optional[int] = Field(default=None, ge=0)


class RelationshipInput(BaseModel):
    id: Optional[str] = None
    source_entity_id: str
    target_entity_id: str
    relationship_type: str = Field(min_length=1)
    source_case_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    why_linked: str = Field(min_length=1)
    evidence_record_id: Optional[str] = None


class AlertStatus(str, Enum):
    NEW = "NEW"
    ACKNOWLEDGED = "ACKNOWLEDGED"


class Alert(BaseModel):
    id: str
    case_ids: list[str]
    shared_entity_ids: list[str]
    severity: str
    status: AlertStatus
    title: str
    explanation: str
    created_at: str


class RawFirInput(BaseModel):
    case_id: str = Field(min_length=1, max_length=200)
    raw_text: str = Field(min_length=1, max_length=500_000)
    source_field: str = "fir_text"
    district: Optional[str] = None
    fir_number: Optional[str] = None


class FirAnalysisRequest(BaseModel):
    firs: list[RawFirInput] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique_case_ids(self):
        case_ids = [fir.case_id for fir in self.firs]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("case_id values must be unique within a batch")
        return self
