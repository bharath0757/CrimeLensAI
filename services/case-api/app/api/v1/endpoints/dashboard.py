from typing import Any
from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from app.schemas.dashboard import DashboardSummaryResponse, DashboardStatisticsResponse
from app.schemas.case import CaseStatus
from app.schemas.user import UserResponse
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.repositories.user_repo import UserRepositoryInterface
from app.api.deps import (
    get_case_repository,
    get_document_repository,
    get_entity_repository,
    get_relationship_repository,
    get_user_repository,
    get_current_user,
)

router = APIRouter()


@router.get("/summary", response_model=DashboardSummaryResponse, summary="Get Dashboard Overview Metrics")
async def get_dashboard_summary(
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> Any:
    """Retrieve top-level counts for dashboard summary widgets."""
    total_cases = await case_repo.count()
    active_cases = await case_repo.count(status=CaseStatus.OPEN) + await case_repo.count(status=CaseStatus.IN_PROGRESS)
    closed_cases = await case_repo.count(status=CaseStatus.CLOSED)
    total_docs = await doc_repo.count()
    total_ents = await ent_repo.count()
    total_rels = await rel_repo.count()
    total_users = await user_repo.count()

    return DashboardSummaryResponse(
        total_cases=total_cases,
        active_cases=active_cases,
        closed_cases=closed_cases,
        total_documents=total_docs,
        total_entities=total_ents,
        total_relationships=total_rels,
        total_investigators=total_users,
    )


@router.get("/stats", summary="Get Dashboard Stat Cards Metrics")
async def get_dashboard_stats(
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Retrieve stat cards data for investigator dashboard."""
    total_cases = await case_repo.count()
    total_ents = await ent_repo.count()
    total_rels = await rel_repo.count()
    
    pending_reviews = 0
    if hasattr(ent_repo, "_entities"):
        pending_reviews = sum(1 for e in getattr(ent_repo, "_entities", {}).values() if e.get("status", "PENDING") == "PENDING")

    return {
        "totalCases": total_cases,
        "entitiesExtracted": total_ents,
        "crossCaseLinks": total_rels,
        "pendingReviews": pending_reviews,
        "total_cases": total_cases,
        "total_entities": total_ents,
        "cross_case_links": total_rels,
        "pending_reviews": pending_reviews,
    }


@router.get("/statistics", response_model=DashboardStatisticsResponse, summary="Get Dashboard Breakdown Statistics")
async def get_dashboard_statistics(
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Retrieve categorized breakdown charts data (status, priority, entity types, activity feed)."""
    cases, _ = await case_repo.list_cases(limit=100)
    
    cases_by_status = {}
    cases_by_priority = {}
    for c in cases:
        st = c.status.value
        pr = c.priority.value
        cases_by_status[st] = cases_by_status.get(st, 0) + 1
        cases_by_priority[pr] = cases_by_priority.get(pr, 0) + 1

    entities_by_type = await ent_repo.count_by_type()
    relationships_by_type = await rel_repo.count_by_type()

    recent_activities = [
        {
            "id": "act-001",
            "type": "CASE_CREATED",
            "description": "Operation CyberLabyrinth created",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "admin@crimelens.ai",
        },
        {
            "id": "act-002",
            "type": "SYSTEM_HEALTH",
            "description": "CrimeLens AI backend services online",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user": "system",
        },
    ]

    return DashboardStatisticsResponse(
        cases_by_status=cases_by_status,
        cases_by_priority=cases_by_priority,
        entities_by_type=entities_by_type,
        relationships_by_type=relationships_by_type,
        documents_by_status={"TOTAL": await doc_repo.count()},
        recent_activities=recent_activities,
    )
