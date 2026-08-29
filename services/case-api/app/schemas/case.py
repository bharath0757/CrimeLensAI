"""
Case schemas for the Case API.
Mirrors the CaseCreate / CaseResponse from contracts/python/schemas.py
with additions for orchestration status tracking.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.schemas.entity import ExtractedEntity


class CaseCreate(BaseModel):
    """POST /api/v1/cases request body."""
    title: str
    fir_text: Optional[str] = None
    call_records: Optional[str] = None
    financial_logs: Optional[str] = None
    location_data: Optional[str] = None
    district: Optional[str] = None
    station: Optional[str] = None
    filing_date: Optional[datetime] = None


class CaseUpdate(BaseModel):
    """PUT /api/v1/cases/{case_id} request body."""
    title: Optional[str] = None
    fir_text: Optional[str] = None
    district: Optional[str] = None
    station: Optional[str] = None
    status: Optional[str] = None


class CaseResponse(BaseModel):
    """Case API response shape matching the OpenAPI contract."""
    id: str
    title: str
    status: str = "DRAFT"
    district: Optional[str] = None
    station: Optional[str] = None
    filing_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    entities: list[ExtractedEntity] = []
    linked_case_count: int = 0
    processing_notes: Optional[str] = None


class DashboardStats(BaseModel):
    """GET /api/v1/dashboard/stats response."""
    total_cases: int = 0
    total_entities: int = 0
    cross_case_links: int = 0
    pending_reviews: int = 0
    cases_by_status: dict[str, int] = {}
