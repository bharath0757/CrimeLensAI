import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError

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
    CaseInsightsResponse,
    CaseLinkageResponse,
    CasePatternsResponse,
    EntityConnectionsResponse,
    EntityNeighborsResponse,
    GraphResponse,
    GraphStats,
    InfluentialPerson,
    LinkCandidate,
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
    current_user: User, case_repo: Cases, ent_repo: Entities, graph_service: Graph,
) -> GraphStats:
    """Retrieve network analytics metrics (density, degree breakdown, top hubs)."""
    await require_case_access(case_id, current_user, case_repo)

    stats = await graph_service.get_graph_stats(case_id)
    masked_hubs = []
    for hub in stats.top_connected_entities:
        item = dict(hub)
        entity_id = item.get("id") or item.get("entity_id")
        entity = await ent_repo.get_by_id(entity_id) if entity_id else None
        if entity and is_victim_pii(entity):
            safe_name = "[VICTIM DATA MASKED]"
            if "name" in item:
                item["name"] = safe_name
            if "entity_name" in item:
                item["entity_name"] = safe_name
            item["is_masked"] = True
        masked_hubs.append(item)
    return stats.model_copy(update={"top_connected_entities": masked_hubs})


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


@router.get(
    "/cases/{case_id}/insights",
    response_model=CaseInsightsResponse,
    summary="Get Case Network Insights",
)
async def get_case_insights(
    case_id: str,
    current_user: User, case_repo: Cases, ent_repo: Entities, graph_service: Graph,
) -> CaseInsightsResponse:
    """Return case-scoped patterns and centrality-ranked people for investigative review."""
    await require_case_access(case_id, current_user, case_repo)

    try:
        raw_patterns = await graph_service.get_case_patterns(case_id)
        patterns = CasePatternsResponse.model_validate(raw_patterns) if raw_patterns is not None else None
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Invalid graph insights response.") from exc
    if patterns is None:
        raise HTTPException(status_code=503, detail="Case insights are temporarily unavailable.")
    if patterns.case_id != case_id:
        raise HTTPException(status_code=502, detail="Invalid graph insights response.")

    entities, _ = await ent_repo.list_by_case(case_id, limit=500)
    local_entity_ids = {entity.id for entity in entities}
    visible_patterns = []
    for pattern in patterns.patterns:
        if case_id not in pattern.case_ids:
            continue
        accessible = True
        for related_case_id in set(pattern.case_ids) - {case_id}:
            try:
                await require_case_access(related_case_id, current_user, case_repo)
            except HTTPException as exc:
                if exc.status_code in {403, 404}:
                    accessible = False
                    break
                raise
        if not accessible:
            continue
        visible_patterns.append(pattern.model_copy(update={
            "supporting_entity_ids": [
                entity_id for entity_id in pattern.supporting_entity_ids
                if entity_id in local_entity_ids
            ],
            "explanation": _safe_pattern_explanation(pattern.pattern_type, len(pattern.case_ids)),
            "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
        }))

    link_candidates: list[LinkCandidate] = []
    link_predictions_unavailable = False
    try:
        raw_candidates = await graph_service.get_case_link_predictions(case_id)
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Invalid graph link-prediction response.") from exc
    except (RuntimeError, TypeError):
        # A missing optional analytics capability must not take down the graph view.
        raw_candidates = None
        link_predictions_unavailable = True
    if raw_candidates is None or not isinstance(raw_candidates, list):
        link_predictions_unavailable = True
    else:
        by_id = {entity.id: entity for entity in entities}
        for raw_candidate in raw_candidates:
            try:
                candidate = LinkCandidate.model_validate(raw_candidate)
            except ValidationError as exc:
                raise HTTPException(status_code=502, detail="Invalid graph link-prediction response.") from exc
            source = by_id.get(candidate.source_entity_id)
            target = by_id.get(candidate.target_entity_id)
            if not source or not target:
                continue
            source_safe = masked_entity(source)
            target_safe = masked_entity(target)
            link_candidates.append(candidate.model_copy(update={
                "source_name": source_safe.name,
                "target_name": target_safe.name,
                "common_neighbor_ids": [
                    entity_id for entity_id in candidate.common_neighbor_ids
                    if entity_id in local_entity_ids
                ],
                "explanation": _safe_link_candidate_explanation(
                    len(candidate.common_neighbor_ids),
                ),
                "disposition": "INVESTIGATIVE_LEAD_NOT_FACT",
            }))
    link_candidates.sort(
        key=lambda item: (-item.confidence, item.source_entity_id, item.target_entity_id),
    )

    people = [entity for entity in entities if entity.entity_type.value == "PERSON"]
    centrality_slots = asyncio.Semaphore(8)

    async def get_centrality(entity_id: str):
        async with centrality_slots:
            return await graph_service.get_entity_centrality(entity_id)

    results = await asyncio.gather(
        *(get_centrality(entity.id) for entity in people),
        return_exceptions=True,
    )
    influential_people = []
    unavailable = 0
    for entity, result in zip(people, results, strict=True):
        if isinstance(result, BaseException) or result is None or result.entity_id != entity.id:
            unavailable += 1
            continue
        safe_entity = masked_entity(entity)
        influential_people.append(InfluentialPerson(
            entity_id=entity.id,
            name=safe_entity.name,
            centrality=result.centrality,
            explanation=(
                "This person ranks highly by network position within the available graph. "
                "Centrality indicates connectivity, not identity, involvement, or guilt."
            ),
            is_masked=safe_entity.is_masked,
        ))
    influential_people.sort(
        key=lambda item: (
            -item.centrality.betweenness,
            -item.centrality.pagerank,
            -item.centrality.degree,
            item.entity_id,
        )
    )
    warnings = []
    if unavailable:
        warnings.append(f"Centrality was unavailable for {unavailable} person record(s).")
    if link_predictions_unavailable:
        warnings.append("Link-prediction analytics are temporarily unavailable.")
    return CaseInsightsResponse(
        case_id=case_id,
        patterns=visible_patterns,
        influential_people=influential_people[:20],
        link_candidates=link_candidates[:20],
        status="degraded" if warnings else "complete",
        warnings=warnings,
    )


def _safe_pattern_explanation(pattern_type: str, case_count: int) -> str:
    label = pattern_type.replace("_", " ").lower()
    return (
        f"Graph analysis identified a {label} signal across {case_count} accessible case(s). "
        "Review the underlying source records before treating this lead as a conclusion."
    )


def _safe_link_candidate_explanation(common_neighbor_count: int) -> str:
    return (
        "Graph analysis suggests a possible link supported by "
        f"{common_neighbor_count} accessible common neighbour(s). "
        "Review the underlying source records before treating this lead as a conclusion."
    )


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
