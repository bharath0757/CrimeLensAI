"""Case-scoped entity APIs with victim-field privacy and reviewed AI ingestion."""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_case_repository,
    get_current_user,
    get_document_repository,
    get_entity_repository,
    get_relationship_repository,
    require_service_token,
)
from app.core.access import require_case_access
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.schemas.document import ProcessingStatus
from app.schemas.entity import (
    EntityCreate,
    EntityListResponse,
    EntityResponse,
    EntityType,
    EntityUpdate,
    UnmaskRequest,
)
from app.schemas.relationship import (
    AIExtractionIngestRequest,
    AIExtractionIngestResponse,
    RelationshipCreate,
)
from app.schemas.user import UserResponse, UserRole
from app.services.audit_events import record_security_event
from app.services.privacy import masked_entity

router = APIRouter()


@router.post("/cases/{case_id}/entities", response_model=EntityResponse, status_code=201, summary="Create Entity")
async def create_entity(
    case_id: str,
    entity_create: EntityCreate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> EntityResponse:
    await require_case_access(case_id, current_user, case_repo, write=True)
    entity = await ent_repo.create(case_id, entity_create)
    await case_repo.update_counts(case_id, entity_delta=1)
    from app.integrations.graph_integration import graph_service_integration

    await graph_service_integration.sync_entity(case_id, entity)
    return masked_entity(entity)


@router.get("/cases/{case_id}/entities", response_model=EntityListResponse, summary="List Case Entities")
async def list_case_entities(
    case_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    entity_type: EntityType | None = None,
    search: str | None = None,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> EntityListResponse:
    await require_case_access(case_id, current_user, case_repo)
    items, total = await ent_repo.list_by_case(
        case_id, skip=skip, limit=limit, entity_type=entity_type, search_query=search,
    )
    return EntityListResponse(total=total, items=[masked_entity(item) for item in items])


@router.get("/entities/{entity_id}", response_model=EntityResponse, summary="Get Entity Details")
async def get_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> EntityResponse:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo)
    return masked_entity(entity)


@router.post("/entities/{entity_id}/unmask", response_model=EntityResponse, summary="Audited Victim-Data Unmask")
async def unmask_entity(
    entity_id: str,
    request: UnmaskRequest,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> EntityResponse:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo)
    if current_user.role == UserRole.ANALYST:
        raise HTTPException(status_code=403, detail="Analysts cannot unmask victim-identifying data")
    if not masked_entity(entity).is_masked:
        return entity
    await record_security_event(
        actor=current_user.id,
        action="VICTIM_PII_UNMASKED",
        resource_type="ENTITY",
        record_id=entity.id,
        case_id=entity.case_id,
        payload={"reason": request.reason, "entity_type": entity.entity_type.value},
    )
    return entity


@router.put("/entities/{entity_id}", response_model=EntityResponse, summary="Update Entity")
async def update_entity(
    entity_id: str,
    entity_update: EntityUpdate,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> EntityResponse:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo, write=True)
    updated = await ent_repo.update(entity.id, entity_update)
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found.")
    return masked_entity(updated)


@router.delete("/entities/{entity_id}", status_code=204, summary="Delete Entity")
async def delete_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> None:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo, write=True)
    await ent_repo.delete(entity_id)
    await case_repo.update_counts(entity.case_id, entity_delta=-1)


@router.post(
    "/integrations/ai/extraction-results",
    response_model=AIExtractionIngestResponse,
    summary="Ingest AI Extraction Results Contract",
    dependencies=[Depends(require_service_token)],
)
async def ingest_ai_extraction_results(
    payload: AIExtractionIngestRequest,
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> AIExtractionIngestResponse:
    case = await case_repo.get_by_id(payload.case_id)
    document = await doc_repo.get_by_id(payload.document_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found.")
    if not document or document.case_id != payload.case_id:
        raise HTTPException(status_code=404, detail="Document not found in this case.")

    created_entities: dict[str, str] = {}
    for extracted in payload.entities:
        entity = await ent_repo.create(
            payload.case_id,
            EntityCreate(
                name=extracted.name,
                entity_type=extracted.entity_type,
                description=extracted.description,
                properties=extracted.properties,
                confidence_score=extracted.confidence_score,
                source_document_id=payload.document_id,
            ),
        )
        created_entities[extracted.name.casefold()] = entity.id

    relationships_count = 0
    for extracted in payload.relationships:
        source_id = created_entities.get(extracted.source_entity_name.casefold())
        target_id = created_entities.get(extracted.target_entity_name.casefold())
        if not source_id:
            source = await ent_repo.get_by_name_and_case(extracted.source_entity_name, payload.case_id)
            source_id = source.id if source else None
        if not target_id:
            target = await ent_repo.get_by_name_and_case(extracted.target_entity_name, payload.case_id)
            target_id = target.id if target else None
        if source_id and target_id:
            await rel_repo.create(
                payload.case_id,
                RelationshipCreate(
                    source_entity_id=source_id,
                    target_entity_id=target_id,
                    relationship_type=extracted.relationship_type,
                    description=extracted.description,
                    properties=extracted.properties,
                    confidence_score=extracted.confidence_score,
                    source_document_id=payload.document_id,
                ),
            )
            relationships_count += 1

    entity_count = len(payload.entities)
    await doc_repo.update_extraction_counts(payload.document_id, entity_count, relationships_count)
    await doc_repo.update_status(payload.document_id, ProcessingStatus.COMPLETED)
    await case_repo.update_counts(payload.case_id, entity_delta=entity_count, rel_delta=relationships_count)
    return AIExtractionIngestResponse(
        success=True,
        case_id=payload.case_id,
        document_id=payload.document_id,
        entities_created=entity_count,
        relationships_created=relationships_count,
        message="AI extraction results ingested successfully.",
    )


@router.post("/entities/{entity_id}/confirm", response_model=EntityResponse, summary="Confirm Extracted Entity")
async def confirm_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> EntityResponse:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo, write=True)
    updated = await ent_repo.set_review_status(entity.id, "CONFIRMED")
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found.")
    return masked_entity(updated)


@router.post("/entities/{entity_id}/reject", response_model=EntityResponse, summary="Reject Extracted Entity")
async def reject_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> EntityResponse:
    entity = await _accessible_entity(entity_id, current_user, ent_repo, case_repo, write=True)
    updated = await ent_repo.set_review_status(entity.id, "REJECTED")
    if updated is None:
        raise HTTPException(status_code=404, detail="Entity not found.")
    return masked_entity(updated)


async def _accessible_entity(
    entity_id: str,
    user: UserResponse,
    entity_repo: EntityRepositoryInterface,
    case_repo: CaseRepositoryInterface,
    *,
    write: bool = False,
) -> EntityResponse:
    entity = await entity_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    await require_case_access(entity.case_id, user, case_repo, write=write)
    return entity
