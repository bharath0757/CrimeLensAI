"""Authenticated dashboard views of the same case-scoped aggregate snapshot."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_current_user
from app.schemas.dashboard import (
    ConnectionAlert,
    ConnectionAlertPage,
    DashboardMetrics,
    DashboardOverview,
    DashboardStatisticsResponse,
    DashboardSummaryResponse,
)
from app.schemas.user import UserResponse
from app.services.alerts import AlertService, get_alert_service
from app.services.dashboard import DashboardService, get_dashboard_service

router = APIRouter()
User = Annotated[UserResponse, Depends(get_current_user)]
Service = Annotated[DashboardService, Depends(get_dashboard_service)]
Alerts = Annotated[AlertService, Depends(get_alert_service)]


async def snapshot(user: User, service: Service) -> DashboardOverview:
    return await service.overview(user)


Snapshot = Annotated[DashboardOverview, Depends(snapshot)]


@router.get("/overview", response_model=DashboardOverview)
async def overview(data: Snapshot):
    return data


@router.get("/stats", response_model=DashboardMetrics)
async def stats(data: Snapshot):
    return data.metrics


@router.get("/summary", response_model=DashboardSummaryResponse)
async def summary(data: Snapshot):
    return data.summary


@router.get("/statistics", response_model=DashboardStatisticsResponse)
async def statistics(data: Snapshot):
    return data.statistics


@router.get("/alerts", response_model=ConnectionAlertPage)
async def alerts(user: User, service: Alerts, offset: int = Query(0, ge=0), limit: int = Query(20, ge=1, le=100)):
    return await service.list(user, offset, limit)


@router.post("/alerts/{alert_id}/acknowledge", response_model=ConnectionAlert)
async def acknowledge(alert_id: str, user: User, service: Alerts):
    return await service.acknowledge(alert_id, user)
