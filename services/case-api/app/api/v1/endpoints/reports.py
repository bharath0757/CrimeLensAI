"""Authenticated court-oriented evidence report export."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import (
    get_case_repository,
    get_current_user,
    get_document_repository,
    get_entity_repository,
    get_relationship_repository,
)
from app.core.access import require_case_access
from app.integrations.ledger_integration import LedgerService, get_ledger_service
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.schemas.user import UserResponse
from app.services.audit_events import record_security_event
from app.services.evidence_report import render_evidence_report
from app.services.privacy import masked_entity, redact_victim_text

router = APIRouter()
User = Annotated[UserResponse, Depends(get_current_user)]


@router.get(
    "/cases/{case_id}/evidence-report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
    summary="Export Court-Oriented Evidence PDF",
)
async def export_evidence_report(
    case_id: str,
    current_user: User,
    case_repo: Annotated[CaseRepositoryInterface, Depends(get_case_repository)],
    document_repo: Annotated[DocumentRepositoryInterface, Depends(get_document_repository)],
    entity_repo: Annotated[EntityRepositoryInterface, Depends(get_entity_repository)],
    relationship_repo: Annotated[RelationshipRepositoryInterface, Depends(get_relationship_repository)],
    ledger: Annotated[LedgerService, Depends(get_ledger_service)],
) -> Response:
    case = await require_case_access(case_id, current_user, case_repo)
    documents, _ = await document_repo.list_by_case(case_id, limit=200)
    entities, _ = await entity_repo.list_by_case(case_id, limit=500)
    relationships, _ = await relationship_repo.list_by_case(case_id, limit=500)

    records = []
    offset = 0
    while True:
        page = await ledger.chain(200, offset, [case_id])
        records.extend(page.records)
        offset += len(page.records)
        if offset >= page.total:
            break
        if offset >= 5000:
            raise HTTPException(status_code=413, detail="Case audit trail exceeds the 5,000-entry report limit")
    if not records:
        raise HTTPException(status_code=409, detail="The case has no delivered audit records yet; retry shortly")
    newest = max(records, key=lambda item: item.sequence)
    verification = await ledger.verify(newest.id, [case_id])
    if not verification.verified:
        raise HTTPException(status_code=409, detail="Audit integrity verification failed; report export blocked")

    export_event_id = await record_security_event(
        actor=current_user.id,
        action="EVIDENCE_REPORT_EXPORTED",
        resource_type="CASE_REPORT",
        record_id=case_id,
        case_id=case_id,
        payload={"format": "PDF", "masked_victim_fields": True},
    )
    pdf, digest = await asyncio.to_thread(
        render_evidence_report,
        case=case,
        case_summary=redact_victim_text(case.description, entities),
        officer=current_user,
        documents=documents,
        entities=[masked_entity(item) for item in entities],
        relationships=relationships,
        ledger_records=records,
        verification=verification,
        export_event_id=export_event_id,
    )
    filename = f"{case.case_number}-evidence-report.pdf".replace('"', "")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-Report-SHA256": digest,
            "X-Audit-Event-ID": export_event_id,
        },
    )
