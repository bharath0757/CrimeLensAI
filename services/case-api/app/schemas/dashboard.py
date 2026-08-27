from typing import List, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class DashboardSummaryResponse(BaseModel):
    total_cases: int
    active_cases: int
    closed_cases: int
    total_documents: int
    total_entities: int
    total_relationships: int
    total_investigators: int


class DashboardStatisticsResponse(BaseModel):
    cases_by_status: Dict[str, int] = Field(default_factory=dict)
    cases_by_priority: Dict[str, int] = Field(default_factory=dict)
    entities_by_type: Dict[str, int] = Field(default_factory=dict)
    relationships_by_type: Dict[str, int] = Field(default_factory=dict)
    documents_by_status: Dict[str, int] = Field(default_factory=dict)
    recent_activities: List[Dict[str, Any]] = Field(default_factory=list)
