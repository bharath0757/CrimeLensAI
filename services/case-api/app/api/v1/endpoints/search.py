from typing import Any, Optional
from fastapi import APIRouter, Depends, Query

from app.schemas.search import (
    SearchCasesResponse,
    SearchEntitiesResponse,
    SearchDocumentsResponse,
    SearchRelationshipsResponse,
    GlobalSearchResponse,
    GlobalSearchResult,
)
from app.schemas.user import UserResponse
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.api.deps import (
    get_case_repository,
    get_document_repository,
    get_entity_repository,
    get_relationship_repository,
    get_current_user,
)

router = APIRouter()


@router.get("/cases", response_model=SearchCasesResponse, summary="Search Cases")
async def search_cases(
    q: str = Query(..., min_length=1),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
) -> Any:
    """Search cases by title, description, case number, or tags."""
    items, total = await case_repo.list_cases(skip=skip, limit=limit, search_query=q)
    return SearchCasesResponse(query=q, total=total, items=items)


@router.get("/entities", response_model=SearchEntitiesResponse, summary="Search Entities")
async def search_entities(
    q: str = Query(..., min_length=1),
    case_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
) -> Any:
    """Search extracted entities by name, type, or description."""
    items, total = await ent_repo.search(query=q, case_id=case_id, skip=skip, limit=limit)
    return SearchEntitiesResponse(query=q, total=total, items=items)


@router.get("/documents", response_model=SearchDocumentsResponse, summary="Search Documents")
async def search_documents(
    q: str = Query(..., min_length=1),
    case_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
) -> Any:
    """Search evidence documents by filename, file type, or original name."""
    items, total = await doc_repo.search(query=q, case_id=case_id, skip=skip, limit=limit)
    return SearchDocumentsResponse(query=q, total=total, items=items)


@router.get("/relationships", response_model=SearchRelationshipsResponse, summary="Search Relationships")
async def search_relationships(
    q: str = Query(..., min_length=1),
    case_id: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Search relationship edges by type or description."""
    items, total = await rel_repo.search(query=q, case_id=case_id, skip=skip, limit=limit)
    return SearchRelationshipsResponse(query=q, total=total, items=items)


@router.get("/global", response_model=GlobalSearchResponse, summary="Global Unified Multi-Resource Search")
async def global_search(
    q: str = Query(..., min_length=1),
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    rel_repo: RelationshipRepositoryInterface = Depends(get_relationship_repository),
) -> Any:
    """Execute unified search across cases, entities, documents, and relationships."""
    cases, _ = await case_repo.list_cases(search_query=q, limit=10)
    entities, _ = await ent_repo.search(query=q, limit=10)
    documents, _ = await doc_repo.search(query=q, limit=10)
    relationships, _ = await rel_repo.search(query=q, limit=10)

    total_matches = len(cases) + len(entities) + len(documents) + len(relationships)
    results = GlobalSearchResult(
        cases=cases,
        entities=entities,
        documents=documents,
        relationships=relationships,
    )
    return GlobalSearchResponse(query=q, total_matches=total_matches, results=results)
