"""Case-scoped authorization shared by evidence and investigation APIs."""

from fastapi import HTTPException

from app.repositories.case_repo import CaseRepositoryInterface
from app.schemas.case import CaseResponse
from app.schemas.user import UserResponse, UserRole


async def require_case_access(
    case_id: str, user: UserResponse, repository: CaseRepositoryInterface, *, write: bool = False,
) -> CaseResponse:
    case = await repository.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    elevated = user.role == UserRole.ADMIN
    if not elevated and user.id != case.owner_id and user.id not in case.assigned_investigator_ids:
        raise HTTPException(status_code=403, detail="Access denied to this case.")
    if write and user.role == UserRole.ANALYST:
        raise HTTPException(status_code=403, detail="Analysts have read-only evidence access.")
    return case
