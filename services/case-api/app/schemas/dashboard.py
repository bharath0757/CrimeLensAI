from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

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
    cases_by_status: dict[str, int] = Field(default_factory=dict)
    cases_by_priority: dict[str, int] = Field(default_factory=dict)
    entities_by_type: dict[str, int] = Field(default_factory=dict)
    relationships_by_type: dict[str, int] = Field(default_factory=dict)
    documents_by_status: dict[str, int] = Field(default_factory=dict)
    recent_activities: list[dict[str, Any]] = Field(default_factory=list)
    transaction_timeline: list["TransactionDay"] = Field(default_factory=list)


class TransactionDay(BaseModel):
    date: str
    amount: Decimal
    count: int


class DashboardMetrics(BaseModel):
    total_cases: int
    high_risk_cases: int
    linked_networks: int
    money_flow: Decimal | None
    active_investigations: int
    total_entities: int
    total_relationships: int
    pending_reviews: int
    currency: Literal["INR"] = "INR"


class DashboardOverview(BaseModel):
    generated_at: datetime
    data_backend: Literal["postgres", "memory"]
    metrics: DashboardMetrics
    statistics: DashboardStatisticsResponse
    summary: DashboardSummaryResponse


class ConnectionAlert(BaseModel):
    id: str
    case_ids: list[str] = Field(min_length=2)
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    status: Literal["NEW", "ACKNOWLEDGED"]
    title: str
    explanation: str
    created_at: datetime


class ConnectionAlertPage(BaseModel):
    total: int
    unread: int
    items: list[ConnectionAlert]


DashboardStatisticsResponse.model_rebuild()
