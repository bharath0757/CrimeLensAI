from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.relationship import (
    RelationshipResponse,
    RelationshipCreate,
    RelationshipUpdate,
    RelationshipListResponse,
    RelationshipType,
)
from app.schemas.user import UserResponse
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.case_repo import CaseRepositoryInterface
from app.api.deps import (
    get_relationship_repository,
    get_entity_repository,
    get_case_repository,
    get_current_user,
)

router = APIRouter()


@router.post("/cases/{case_id}/relationships", response_model=RelationshipResponse, status_code=status.HTTP_201_CREATED, summary="Create Relationship")
async def create_relationship(
    case_id: str,
    rel_create: RelationshipCreate,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Create a relationship edge between two entities in a case."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    src = await ent_repo.get_by_id(rel_create.source_entity_id)
    tgt = await ent_repo.get_by_id(rel_create.target_entity_id)
    if not src or not tgt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source or target entity not found in repository.")

    relationship = await rel_repo.create(case_id, rel_create)
    await case_repo.update_counts(case_id, rel_delta=1)
    from app.integrations.graph_integration import graph_service_integration
    try:
        await graph_service_integration.sync_relationship(case_id, relationship)
    except Exception as e:
        import logging; logging.error(f'Graph sync failed: {e}')
    return relationship


@router.get("/cases/{case_id}/relationships", response_model=RelationshipListResponse, summary="List Case Relationships")
async def list_case_relationships(
    case_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    relationship_type: Optional[RelationshipType] = None,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """List relationships for a case with optional type filter."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    items, total = await rel_repo.list_by_case(
        case_id,
        skip=skip,
        limit=limit,
        relationship_type=relationship_type,
    )
    return RelationshipListResponse(total=total, items=items)


@router.get("/relationships/{relationship_id}", response_model=RelationshipResponse, summary="Get Relationship Details")
async def get_relationship(
    relationship_id: str,
    current_user: UserResponse = Depends(get_current_user),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Retrieve details for a specific relationship."""
    rel = await rel_repo.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found.")
    return rel


@router.put("/relationships/{relationship_id}", response_model=RelationshipResponse, summary="Update Relationship")
async def update_relationship(
    relationship_id: str,
    rel_update: RelationshipUpdate,
    current_user: UserResponse = Depends(get_current_user),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Update relationship properties or confidence score."""
    rel = await rel_repo.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found.")

    updated_rel = await rel_repo.update(relationship_id, rel_update)
    return updated_rel


@router.delete("/relationships/{relationship_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Relationship")
async def delete_relationship(
    relationship_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> None:
    """Delete a relationship edge."""
    rel = await rel_repo.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found.")

    await rel_repo.delete(relationship_id)
    await case_repo.update_counts(rel.case_id, rel_delta=-1)
    return None
