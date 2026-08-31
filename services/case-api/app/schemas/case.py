from enum import Enum
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.entity import ExtractedEntity

class CaseStatus(str, Enum):
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"

class CasePriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class CaseBase(BaseModel):
    title: str = Field(..., min_length=3, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    priority: CasePriority = CasePriority.MEDIUM
    tags: List[str] = Field(default_factory=list)
    fir_text: Optional[str] = None
    call_records: Optional[str] = None
    financial_logs: Optional[str] = None
    location_data: Optional[str] = None
    district: Optional[str] = None
    station: Optional[str] = None
    filing_date: Optional[datetime] = None

class CaseCreate(CaseBase):
    case_number: Optional[str] = None
    assigned_investigator_ids: List[str] = Field(default_factory=list)

class CaseUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=3, max_length=150)
    description: Optional[str] = Field(None, max_length=2000)
    status: Optional[str] = None
    priority: Optional[CasePriority] = None
    assigned_investigator_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    fir_text: Optional[str] = None
    district: Optional[str] = None
    station: Optional[str] = None

class CaseStatusUpdate(BaseModel):
    status: CaseStatus

class CaseResponse(CaseBase):
    id: str
    case_number: Optional[str] = None
    status: str = "DRAFT"
    owner_id: Optional[str] = None
    assigned_investigator_ids: List[str] = Field(default_factory=list)
    document_count: int = 0
    entity_count: int = 0
    relationship_count: int = 0
    created_at: datetime
    updated_at: datetime
    entities: List[ExtractedEntity] = []
    linked_case_count: int = 0
    processing_notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)

class CaseListResponse(BaseModel):
    total: int
    skip: int
    limit: int
    items: List[CaseResponse]

class DashboardStats(BaseModel):
    total_cases: int = 0
    total_entities: int = 0
    cross_case_links: int = 0
    pending_reviews: int = 0
    cases_by_status: dict = {}
