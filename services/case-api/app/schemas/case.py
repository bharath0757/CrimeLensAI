from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class CaseStatus(StrEnum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CasePriority(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., max_length=2000)
    priority: CasePriority = CasePriority.MEDIUM
    tags: list[str] = Field(default_factory=list)


class CaseCreate(CaseBase):
    case_number: str | None = None
    assigned_investigator_ids: list[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: str | None = Field(None, min_length=3, max_length=150)
    description: str | None = Field(None, max_length=2000)
    status: CaseStatus | None = None
    priority: CasePriority | None = None
    assigned_investigator_ids: list[str] | None = None
    tags: list[str] | None = None


class CaseStatusUpdate(BaseModel):
    status: CaseStatus


class CaseResponse(CaseBase):
    id: str
    case_number: str
    status: CaseStatus
    owner_id: str
    assigned_investigator_ids: list[str] = Field(default_factory=list)
    document_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CaseListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: list[CaseResponse]
