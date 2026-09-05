from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_case_repository,
    get_current_user,
    get_entity_repository,
    get_relationship_repository,
)
from app.core.access import require_case_access
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipListResponse,
    RelationshipResponse,
    RelationshipType,
    RelationshipUpdate,
)
from app.schemas.user import UserResponse

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
    await require_case_access(case_id, current_user, case_repo, write=True)

    src = await ent_repo.get_by_id(rel_create.source_entity_id)
    tgt = await ent_repo.get_by_id(rel_create.target_entity_id)
    if not src or not tgt or src.case_id != case_id or tgt.case_id != case_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source and target must belong to this case.")

    relationship = await rel_repo.create(case_id, rel_create)
    await case_repo.update_counts(case_id, rel_delta=1)
    from app.integrations.graph_integration import graph_service_integration
    await graph_service_integration.sync_relationship(case_id, relationship)
    return relationship


@router.get("/cases/{case_id}/relationships", response_model=RelationshipListResponse, summary="List Case Relationships")
async def list_case_relationships(
    case_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    relationship_type: RelationshipType | None = None,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """List relationships for a case with optional type filter."""
    await require_case_access(case_id, current_user, case_repo)

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
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Retrieve details for a specific relationship."""
    rel = await rel_repo.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found.")
    await require_case_access(rel.case_id, current_user, case_repo)
    return rel


@router.put("/relationships/{relationship_id}", response_model=RelationshipResponse, summary="Update Relationship")
async def update_relationship(
    relationship_id: str,
    rel_update: RelationshipUpdate,
    current_user: UserResponse = Depends(get_current_user),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Update relationship properties or confidence score."""
    rel = await rel_repo.get_by_id(relationship_id)
    if not rel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Relationship not found.")
    await require_case_access(rel.case_id, current_user, case_repo, write=True)

    return await rel_repo.update(relationship_id, rel_update)


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
    await require_case_access(rel.case_id, current_user, case_repo, write=True)

    await rel_repo.delete(relationship_id)
    await case_repo.update_counts(rel.case_id, rel_delta=-1)
