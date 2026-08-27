from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict


class CaseStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CaseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: str = Field(..., max_length=2000)
    priority: CasePriority = CasePriority.MEDIUM
    tags: List[str] = Field(default_factory=list)


class CaseCreate(CaseBase):
    case_number: Optional[str] = None
    assigned_investigator_ids: List[str] = Field(default_factory=list)


class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[CaseStatus] = None
    priority: Optional[CasePriority] = None
    assigned_investigator_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class CaseStatusUpdate(BaseModel):
    status: CaseStatus


class CaseResponse(CaseBase):
    id: str
    case_number: str
    status: CaseStatus
    owner_id: str
    assigned_investigator_ids: List[str] = Field(default_factory=list)
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
    items: List[CaseResponse]
