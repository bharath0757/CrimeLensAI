from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.case import (
    CaseResponse,
    CaseCreate,
    CaseUpdate,
    CaseStatusUpdate,
    CaseListResponse,
    CaseStatus,
    CasePriority,
)
from app.schemas.user import UserResponse, UserRole
from app.repositories.case_repo import CaseRepositoryInterface
from app.api.deps import get_case_repository, get_current_user

router = APIRouter()


@router.post("", response_model=CaseResponse, status_code=status.HTTP_201_CREATED, summary="Create New Case")
async def create_case(
    case_create: CaseCreate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Create a new crime investigation case."""
    case = await case_repo.create(case_create, owner_id=current_user.id)
    return case


@router.get("", response_model=CaseListResponse, summary="List Cases")
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    case_status: Optional[CaseStatus] = Query(None, alias="status"),
    priority: Optional[CasePriority] = None,
    search: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """List cases accessible to the investigator with optional filters and pagination."""
    owner_id = None if current_user.role in [UserRole.ADMIN, UserRole.LEAD_INVESTIGATOR] else current_user.id
    items, total = await case_repo.list_cases(
        skip=skip,
        limit=limit,
        status=case_status,
        priority=priority,
        owner_id=owner_id,
        search_query=search,
    )
    return CaseListResponse(total=total, skip=skip, limit=limit, items=items)


@router.get("/{case_id}", response_model=CaseResponse, summary="Get Case Details")
async def get_case(
    case_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Retrieve detailed metadata for a specific case."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
    
    # Access check
    if current_user.role not in [UserRole.ADMIN, UserRole.LEAD_INVESTIGATOR]:
        if case.owner_id != current_user.id and current_user.id not in case.assigned_investigator_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this case.")
            
    return case


@router.put("/{case_id}", response_model=CaseResponse, summary="Update Case")
async def update_case(
    case_id: str,
    case_update: CaseUpdate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Update case title, description, priority, tags, or assigned investigators."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")
        
    if current_user.role not in [UserRole.ADMIN, UserRole.LEAD_INVESTIGATOR] and case.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this case.")

    updated_case = await case_repo.update(case_id, case_update)
    return updated_case


@router.patch("/{case_id}/status", response_model=CaseResponse, summary="Change Case Status")
async def update_case_status(
    case_id: str,
    status_update: CaseStatusUpdate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Change status of a case (e.g. OPEN -> CLOSED)."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    if current_user.role not in [UserRole.ADMIN, UserRole.LEAD_INVESTIGATOR] and case.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to update status.")

    updated_case = await case_repo.update(case_id, CaseUpdate(status=status_update.status))
    return updated_case


@router.delete("/{case_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete / Archive Case")
async def delete_case(
    case_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> None:
    """Delete a case (Admin or Case Owner only)."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    if current_user.role != UserRole.ADMIN and case.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admins or Case Owners can delete a case.")

    await case_repo.delete(case_id)
    return None
