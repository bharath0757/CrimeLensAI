import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import (
    get_case_repository,
    get_current_user,
    get_entity_repository,
    get_graph_service,
)
from app.core.access import require_case_access
from app.integrations.graph_integration import GraphServiceInterface
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.schemas.graph import (
    CaseLinkageResponse,
    EntityConnectionsResponse,
    EntityNeighborsResponse,
    GraphResponse,
    GraphStats,
    ShortestPathResponse,
)
from app.schemas.user import UserResponse
from app.services.linkage_scoring import enrich_case_linkage
from app.services.privacy import is_victim_pii, masked_entity

router = APIRouter()
User = Annotated[UserResponse, Depends(get_current_user)]
Cases = Annotated[CaseRepositoryInterface, Depends(get_case_repository)]
Entities = Annotated[EntityRepositoryInterface, Depends(get_entity_repository)]
Graph = Annotated[GraphServiceInterface, Depends(get_graph_service)]


@router.get("/cases/{case_id}/graph", response_model=GraphResponse, summary="Get Case Network Graph Topology")
async def get_case_graph(
    case_id: str,
    current_user: User, case_repo: Cases, ent_repo: Entities, graph_service: Graph,
) -> GraphResponse:
    """Retrieve full network graph topology payload ({ nodes: [...], edges: [...] }) for a case."""
    await require_case_access(case_id, current_user, case_repo)

    graph = await graph_service.get_case_graph(case_id)
    return graph.model_copy(update={"nodes": await _mask_graph_nodes(graph.nodes, ent_repo)})


@router.get("/entities/{entity_id}/connections", response_model=EntityConnectionsResponse, summary="Get Direct Entity Connections")
async def get_entity_connections(
    entity_id: str,
    current_user: User, ent_repo: Entities, case_repo: Cases, graph_service: Graph,
) -> EntityConnectionsResponse:
    """Retrieve direct connected edges and neighbor nodes for an entity."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    await require_case_access(entity.case_id, current_user, case_repo)

    connections = await graph_service.get_entity_connections(entity_id)
    if not connections:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity connections not found.")
    masked_source = masked_entity(entity)
    return connections.model_copy(update={
        "entity_name": masked_source.name,
        "connected_nodes": await _mask_graph_nodes(connections.connected_nodes, ent_repo),
    })


@router.get("/entities/{entity_id}/neighbors", response_model=EntityNeighborsResponse, summary="Get Entity Neighborhood Graph")
async def get_entity_neighbors(
    entity_id: str,
    current_user: User, ent_repo: Entities, case_repo: Cases, graph_service: Graph,
    depth: int = Query(1, ge=1, le=5, description="Search depth / k-hop distance"),
) -> EntityNeighborsResponse:
    """Retrieve k-hop neighborhood subgraph surrounding an entity."""
    entity = await ent_repo.get_by_id(entity_id)
    if not entity:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Entity not found.")

    await require_case_access(entity.case_id, current_user, case_repo)

    neighbors = await graph_service.get_entity_neighbors(entity_id, depth=depth)
    if not neighbors:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Neighborhood graph not found.")
    return neighbors.model_copy(update={"nodes": await _mask_graph_nodes(neighbors.nodes, ent_repo)})


@router.get("/cases/{case_id}/graph/stats", response_model=GraphStats, summary="Get Case Network Statistics")
async def get_graph_stats(
    case_id: str,
    current_user: User, case_repo: Cases, graph_service: Graph,
) -> GraphStats:
    """Retrieve network analytics metrics (density, degree breakdown, top hubs)."""
    await require_case_access(case_id, current_user, case_repo)

    return await graph_service.get_graph_stats(case_id)


@router.get("/cases/{case_id}/graph/shortest-path", response_model=ShortestPathResponse, summary="Find Shortest Network Path")
async def get_shortest_path(
    case_id: str,
    current_user: User, case_repo: Cases, ent_repo: Entities, graph_service: Graph,
    source_entity_id: str = Query(..., description="Source entity ID"),
    target_entity_id: str = Query(..., description="Target entity ID"),
) -> ShortestPathResponse:
    """Compute shortest network path connecting two entities in a case graph."""
    await require_case_access(case_id, current_user, case_repo)
    for entity_id in (source_entity_id, target_entity_id):
        entity = await ent_repo.get_by_id(entity_id)
        if not entity or entity.case_id != case_id:
            raise HTTPException(status_code=404, detail="Path endpoint not found in this case.")

    path = await graph_service.get_shortest_path(source_entity_id, target_entity_id)
    return path.model_copy(update={"nodes": await _mask_graph_nodes(path.nodes, ent_repo)})

@router.get("/cases/{case_id}/linkage", response_model=CaseLinkageResponse, summary="Get Cross-Case Linkage")
async def get_case_linkage(
    case_id: str,
    current_user: User, case_repo: Cases, ent_repo: Entities, graph_service: Graph,
) -> CaseLinkageResponse:
    """Find cases linked to the specified case through shared entities."""
    await require_case_access(case_id, current_user, case_repo)
    payload = await enrich_case_linkage(case_id, await graph_service.get_case_linkage(case_id))
    try:
        linkage = CaseLinkageResponse.model_validate(payload)
        if linkage.case_id != case_id:
            raise ValueError("Unexpected source case")
    except ValueError as exc:
        raise HTTPException(status_code=502, detail="Invalid graph linkage response") from exc
    visible = []
    victim_values = await _victim_values(case_id, ent_repo)
    for linked in linkage.linked_cases:
        try:
            await require_case_access(linked.case_id, current_user, case_repo)
        except HTTPException as exc:
            if exc.status_code in {403, 404}:
                continue
            raise
        protected_values = victim_values | await _victim_values(linked.case_id, ent_repo)
        shared = []
        for item in linked.shared_entities:
            entity = await ent_repo.get_by_id(item.entity_id) if item.entity_id else None
            values = {str(item.value).strip().casefold(), str(item.canonical_value or "").strip().casefold()}
            if (entity and is_victim_pii(entity)) or bool(values & protected_values):
                shared.append(item.model_copy(update={
                    "value": "[VICTIM DATA MASKED]",
                    "canonical_value": "[VICTIM DATA MASKED]",
                    "is_masked": True,
                }))
            else:
                shared.append(item)
        visible.append(linked.model_copy(update={"shared_entities": shared}))
    return linkage.model_copy(update={"linked_cases": visible})


async def _mask_graph_nodes(nodes, ent_repo: EntityRepositoryInterface):
    """Apply the same default victim masking to every graph-shaped API response."""
    entities = await asyncio.gather(*(ent_repo.get_by_id(node.id) for node in nodes))
    protected = {entity.id: masked_entity(entity) for entity in entities if entity and is_victim_pii(entity)}
    return [
        node.model_copy(update={
            "label": protected[node.id].name,
            "properties": protected[node.id].properties | {"is_masked": True},
        })
        if node.id in protected else node
        for node in nodes
    ]


async def _victim_values(case_id: str, ent_repo: EntityRepositoryInterface) -> set[str]:
    values: set[str] = set()
    skip = 0
    while True:
        items, total = await ent_repo.list_by_case(case_id, skip=skip, limit=200)
        for entity in items:
            if not is_victim_pii(entity):
                continue
            values.add(entity.name.strip().casefold())
            properties = entity.properties or {}
            normalized = properties.get("normalized_value")
            if isinstance(normalized, str):
                values.add(normalized.strip().casefold())
            for occurrence in properties.get("occurrences", []):
                if not isinstance(occurrence, dict):
                    continue
                for key in ("value", "normalized_value", "name"):
                    candidate = occurrence.get(key)
                    if isinstance(candidate, str):
                        values.add(candidate.strip().casefold())
        skip += len(items)
        if not items or skip >= total:
            return {value for value in values if value}
