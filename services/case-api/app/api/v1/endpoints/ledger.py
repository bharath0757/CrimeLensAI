"""Case-scoped audit browsing and explicit hash-chain verification."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.deps import get_case_repository, get_current_user
from app.core.access import require_case_access
from app.integrations.ledger_integration import LedgerService, get_ledger_service
from app.repositories.case_repo import CaseRepositoryInterface
from app.schemas.ledger import (
    LedgerChainResponse,
    LedgerRecordResponse,
    LedgerVerificationResponse,
)
from app.schemas.user import UserResponse, UserRole

router = APIRouter()
User = Annotated[UserResponse, Depends(get_current_user)]
Cases = Annotated[CaseRepositoryInterface, Depends(get_case_repository)]
Ledger = Annotated[LedgerService, Depends(get_ledger_service)]


async def accessible_cases(user: UserResponse, cases: CaseRepositoryInterface, case_id: str | None):
    if case_id:
        await require_case_access(case_id, user, cases)
        return [case_id]
    if user.role == UserRole.ADMIN:
        return None
    items, total = await cases.list_cases(owner_id=user.id, limit=1001)
    if total > 1000:
        raise HTTPException(status_code=422, detail="Select a case to browse its audit trail")
    return [item.id for item in items]


@router.get("/chain", response_model=LedgerChainResponse)
async def get_ledger_chain(
    current_user: User, case_repo: Cases, ledger: Ledger,
    limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    case_id: str | None = None,
) -> LedgerChainResponse:
    scope = await accessible_cases(current_user, case_repo, case_id)
    if scope == []:
        return LedgerChainResponse(total=0, offset=offset, limit=limit, items=[])
    chain = await ledger.chain(limit, offset, scope)
    if scope is not None and any(record.case_id not in scope for record in chain.records):
        raise HTTPException(status_code=502, detail="Audit service returned an out-of-scope record")
    return LedgerChainResponse(total=chain.total, offset=chain.offset, limit=chain.limit, items=[
        LedgerRecordResponse(
            id=record.id, sequence=record.sequence, timestamp=record.timestamp,
            action=record.action, actor=record.actor,
            resource=f"{record.resource_type}: {record.record_id}",
            dataHash=record.hash, previous_hash=record.previous_hash,
        ) for record in chain.records
    ])


@router.get("/verify/{record_id}", response_model=LedgerVerificationResponse)
async def verify_ledger_record(
    record_id: str, current_user: User, case_repo: Cases, ledger: Ledger,
    case_id: str | None = None,
) -> LedgerVerificationResponse:
    scope = await accessible_cases(current_user, case_repo, case_id)
    if scope == []:
        raise HTTPException(status_code=404, detail="Audit record not found")
    result = await ledger.verify(record_id, scope)
    if scope is not None and result.case_id not in scope:
        raise HTTPException(status_code=502, detail="Audit service returned an out-of-scope verification")
    return result
