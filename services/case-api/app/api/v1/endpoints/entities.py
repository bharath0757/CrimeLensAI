from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.entity import (
    EntityResponse,
    EntityCreate,
    EntityUpdate,
    EntityListResponse,
    EntityType,
)
from app.schemas.relationship import (
    AIExtractionIngestRequest,
    AIExtractionIngestResponse,
    RelationshipCreate,
)
from app.schemas.user import UserResponse
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.schemas.document import ProcessingStatus
from app.api.deps import (
    get_entity_repository,
    get_relationship_repository,
    get_case_repository,
    get_document_repository,
    get_current_user,
)

router = APIRouter()


@router.post("/cases/{case_id}/entities", response_model=EntityResponse, status_code=status.HTTP_201_CREATED, summary="Create Entity")
async def create_entity(
    case_id: str,
    entity_create: EntityCreate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    """Manually add or associate an entity with a case."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    entity = await ent_repo.create(case_id, entity_create)
    await case_repo.update_counts(case_id, entity_delta=1)
    return entity


@router.get("/cases/{case_id}/entities", response_model=EntityListResponse, summary="List Case Entities")
async def list_case_entities(
    case_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    entity_type: Optional[EntityType] = None,
    search: Optional[str] = None,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    """List entities for a case with optional type filter and search query."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    items, total = await ent_repo.list_by_case(
        case_id,
        skip=skip,
        limit=limit,
        entity_type=entity_type,
        search_query=search,
    )
    return EntityListResponse(total=total, items=items)


@router.get("/entities/{entity_id}", response_model=EntityResponse, summary="Get Entity Details")
async def get_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    """Retrieve detailed metadata for a specific entity."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    return entity


@router.put("/entities/{entity_id}", response_model=EntityResponse, summary="Update Entity")
async def update_entity(
    entity_id: str,
    entity_update: EntityUpdate,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    """Update entity fields or properties."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    updated_entity = await ent_repo.update(entity_id, entity_update)
    return updated_entity


@router.delete("/entities/{entity_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Entity")
async def delete_entity(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> None:
    """Delete an entity from a case."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    await ent_repo.delete(entity_id)
    await case_repo.update_counts(entity.case_id, entity_delta=-1)
    return None


@router.post("/integrations/ai/extraction-results", response_model=AIExtractionIngestResponse, summary="Ingest AI Extraction Results Contract")
async def ingest_ai_extraction_results(
    payload: AIExtractionIngestRequest,
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """
    Interface Contract Endpoint for the AI/NLP teammate to send extracted entities and relationships
    from their document processing model.
    """
    case = await case_repo.get_by_id(payload.case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    document = await doc_repo.get_by_id(payload.document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    created_entities_map = {}
    entities_count = 0

    for e in payload.entities:
        ent_obj = await ent_repo.create(
            case_id=payload.case_id,
            entity_create=EntityCreate(
                name=e.name,
                entity_type=e.entity_type,
                description=e.description,
                properties=e.properties,
                confidence_score=e.confidence_score,
                source_document_id=payload.document_id,
            ),
        )
        created_entities_map[e.name.lower()] = ent_obj.id
        entities_count += 1

    relationships_count = 0
    for r in payload.relationships:
        src_id = created_entities_map.get(r.source_entity_name.lower())
        tgt_id = created_entities_map.get(r.target_entity_name.lower())

        if not src_id:
            src_ent = await ent_repo.get_by_name_and_case(r.source_entity_name, payload.case_id)
            if src_ent:
                src_id = src_ent.id
        if not tgt_id:
            tgt_ent = await ent_repo.get_by_name_and_case(r.target_entity_name, payload.case_id)
            if tgt_ent:
                tgt_id = tgt_ent.id

        if src_id and tgt_id:
            await rel_repo.create(
                case_id=payload.case_id,
                rel_create=RelationshipCreate(
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relationship_type=r.relationship_type,
                    description=r.description,
                    properties=r.properties,
                    confidence_score=r.confidence_score,
                    source_document_id=payload.document_id,
                ),
            )
            relationships_count += 1

    await doc_repo.update_extraction_counts(payload.document_id, entities_count, relationships_count)
    await doc_repo.update_status(payload.document_id, ProcessingStatus.COMPLETED)
    await case_repo.update_counts(payload.case_id, entity_delta=entities_count, rel_delta=relationships_count)

    return AIExtractionIngestResponse(
        success=True,
        case_id=payload.case_id,
        document_id=payload.document_id,
        entities_created=entities_count,
        relationships_created=relationships_count,
        message="AI extraction results ingested successfully.",
    )


@router.post("/entities/{entity_id}/confirm", response_model=EntityResponse, summary="Confirm Extracted Entity")
async def confirm_entity(
    entity_id: str,
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    if hasattr(ent_repo, "_entities") and entity_id in getattr(ent_repo, "_entities", {}):
        ent_repo._entities[entity_id]["status"] = "CONFIRMED"
    return await ent_repo.get_by_id(entity_id)


@router.post("/entities/{entity_id}/reject", response_model=EntityResponse, summary="Reject Extracted Entity")
async def reject_entity(
    entity_id: str,
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")
    if hasattr(ent_repo, "_entities") and entity_id in getattr(ent_repo, "_entities", {}):
        ent_repo._entities[entity_id]["status"] = "REJECTED"
    return await ent_repo.get_by_id(entity_id)
