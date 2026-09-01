from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.schemas.graph import (
    GraphResponse,
    GraphStats,
    EntityConnectionsResponse,
    EntityNeighborsResponse,
    ShortestPathResponse,
)
from app.schemas.user import UserResponse
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.integrations.graph_integration import GraphServiceInterface
from app.api.deps import (
    get_graph_service,
    get_case_repository,
    get_entity_repository,
    get_current_user,
)

router = APIRouter()


@router.get("/cases/{case_id}/graph", response_model=GraphResponse, summary="Get Case Network Graph Topology")
async def get_case_graph(
    case_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Retrieve full network graph topology payload ({ nodes: [...], edges: [...] }) for a case."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    graph_payload = await graph_service.get_case_graph(case_id)
    return graph_payload


@router.get("/entities/{entity_id}/connections", response_model=EntityConnectionsResponse, summary="Get Direct Entity Connections")
async def get_entity_connections(
    entity_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Retrieve direct connected edges and neighbor nodes for an entity."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    connections = await graph_service.get_entity_connections(entity_id)
    if not connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity connections not found.")
    return connections


@router.get("/entities/{entity_id}/neighbors", response_model=EntityNeighborsResponse, summary="Get Entity Neighborhood Graph")
async def get_entity_neighbors(
    entity_id: str,
    depth: int = Query(1, ge=1, le=5, description="Search depth / k-hop distance"),
    current_user: UserResponse = Depends(get_current_user),
    ent_repo: EntityRepositoryInterface = Depends(get_entity_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Retrieve k-hop neighborhood subgraph surrounding an entity."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    neighbors = await graph_service.get_entity_neighbors(entity_id, depth=depth)
    if not neighbors:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Neighborhood graph not found.")
    return neighbors


@router.get("/cases/{case_id}/graph/stats", response_model=GraphStats, summary="Get Case Network Statistics")
async def get_graph_stats(
    case_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Retrieve network analytics metrics (density, degree breakdown, top hubs)."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    stats = await graph_service.get_graph_stats(case_id)
    return stats


@router.get("/cases/{case_id}/graph/shortest-path", response_model=ShortestPathResponse, summary="Find Shortest Network Path")
async def get_shortest_path(
    case_id: str,
    source_entity_id: str = Query(..., description="Source entity ID"),
    target_entity_id: str = Query(..., description="Target entity ID"),
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Compute shortest network path connecting two entities in a case graph."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    path_result = await graph_service.get_shortest_path(source_entity_id, target_entity_id)
    return path_result

@router.get("/cases/{case_id}/linkage", summary="Get Cross-Case Linkage")
async def get_case_linkage(
    case_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    graph_service: GraphServiceInterface = Depends(get_graph_service),
) -> Any:
    """Find cases linked to the specified case through shared entities."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    linkage = await graph_service.get_case_linkage(case_id)
    return linkage
