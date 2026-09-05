"""Case API adapter for graph persistence and read-side network views."""

from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from collections import deque
from itertools import pairwise
from typing import Any

import httpx

from app.core.config import settings
from app.core.entity_identity import normalized_entity_value
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.registry import entity_repository, relationship_repository
from app.repositories.relationship_repo import (
    RelationshipRepositoryInterface,
)
from app.schemas.graph import (
    EntityConnectionsResponse,
    EntityNeighborsResponse,
    GraphEdge,
    GraphNode,
    GraphResponse,
    GraphStats,
    ShortestPathResponse,
)

logger = logging.getLogger(__name__)

GRAPH_ENTITY_TYPES = {
    "PHONE_NUMBER": "PHONE",
    "ORGANIZATION": "ORG",
    "BANK_ACCOUNT": "BANK_ACCOUNT",
}
GRAPH_RELATIONSHIP_TYPES = {
    "COMMUNICATED_WITH": "CALLED",
    "TRANSFERRED_FUNDS": "TRANSFERRED_TO",
    "OWNER_OF": "OWNS",
}


class GraphServiceInterface(ABC):
    @abstractmethod
    async def sync_entity(self, case_id: str, entity: Any) -> None: ...

    @abstractmethod
    async def sync_relationship(self, case_id: str, relationship: Any) -> None: ...

    @abstractmethod
    async def get_case_graph(self, case_id: str) -> GraphResponse: ...

    @abstractmethod
    async def get_entity_connections(
        self, entity_id: str,
    ) -> EntityConnectionsResponse | None: ...

    @abstractmethod
    async def get_entity_neighbors(
        self, entity_id: str, depth: int = 1,
    ) -> EntityNeighborsResponse | None: ...

    @abstractmethod
    async def get_graph_stats(self, case_id: str) -> GraphStats: ...

    @abstractmethod
    async def get_case_linkage(self, case_id: str) -> dict[str, Any]: ...

    @abstractmethod
    async def get_shortest_path(
        self, source_entity_id: str, target_entity_id: str,
    ) -> ShortestPathResponse: ...


class IntegratedGraphService(GraphServiceInterface):
    """Keep local API reads responsive while mirroring writes to Neo4j."""

    def __init__(
        self,
        ent_repo: EntityRepositoryInterface = entity_repository,
        rel_repo: RelationshipRepositoryInterface = relationship_repository,
        base_url: str | None = None,
    ) -> None:
        self._ent_repo = ent_repo
        self._rel_repo = rel_repo
        configured = base_url or settings.GRAPH_SERVICE_URL
        self._base_url = configured.rstrip("/") + "/api/v1"

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.request(
                    method,
                    f"{self._base_url}{path}",
                    json=json,
                    params=params,
                    headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN},
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            logger.warning("Graph service request failed: %s %s (%s)", method, path, type(exc).__name__)
            if method != "GET" and settings.DATA_BACKEND == "postgres":
                raise
            return None

    @staticmethod
    def _graph_entity_id(entity: Any) -> str:
        kind = GRAPH_ENTITY_TYPES.get(entity.entity_type.value, entity.entity_type.value)
        value = entity.name
        canonical = normalized_entity_value(kind, value)
        return str(uuid.uuid5(uuid.NAMESPACE_URL, f"crimelens:entity:{kind}:{canonical}"))

    async def sync_entity(self, case_id: str, entity: Any) -> None:
        entity_type = GRAPH_ENTITY_TYPES.get(entity.entity_type.value, entity.entity_type.value)
        for occurrence in entity.properties.get("occurrences") or [{}]:
            await self._request(
                "POST", "/entities",
                json={
                    "case_id": case_id,
                    "entity_id": self._graph_entity_id(entity),
                    "entity_type": entity_type,
                    "value": occurrence.get("value", entity.name),
                    "normalized_value": normalized_entity_value(entity_type, entity.name),
                    "confidence": entity.confidence_score,
                    "source_field": occurrence.get("document_id", "case_api"),
                    "start_offset": occurrence.get("start_offset"),
                    "end_offset": occurrence.get("end_offset"),
                },
            )

    async def sync_relationship(self, case_id: str, relationship: Any) -> None:
        relation_type = GRAPH_RELATIONSHIP_TYPES.get(
            relationship.relationship_type.value,
            relationship.relationship_type.value,
        )
        source = await self._ent_repo.get_by_id(relationship.source_entity_id)
        target = await self._ent_repo.get_by_id(relationship.target_entity_id)
        if not source or not target or source.case_id != case_id or target.case_id != case_id:
            raise ValueError("Relationship endpoints must belong to the case")
        await self.sync_entity(case_id, source)
        await self.sync_entity(case_id, target)
        await self._request(
            "POST",
            "/relationships",
            json={
                "source_entity_id": self._graph_entity_id(source),
                "target_entity_id": self._graph_entity_id(target),
                "relationship_type": relation_type,
                "source_case_id": case_id,
                "confidence": relationship.confidence_score,
                "why_linked": relationship.description
                or f"Observed in case {case_id}",
                "evidence_record_id": relationship.properties.get("transaction_id")
                or relationship.properties.get("cdr_id") or relationship.id,
            },
        )

    @staticmethod
    def _node(entity: Any) -> GraphNode:
        return GraphNode(
            id=entity.id,
            label=entity.name,
            type=entity.entity_type.value,
            properties=entity.properties,
            confidence_score=entity.confidence_score,
        )

    @staticmethod
    def _edge(relationship: Any) -> GraphEdge:
        return GraphEdge(
            id=relationship.id,
            source=relationship.source_entity_id,
            target=relationship.target_entity_id,
            label=relationship.relationship_type.value,
            type=relationship.relationship_type.value,
            properties=relationship.properties,
            confidence_score=relationship.confidence_score,
        )

    async def get_case_graph(self, case_id: str) -> GraphResponse:
        entities, _ = await self._ent_repo.list_by_case(case_id, limit=500)
        relationships, _ = await self._rel_repo.list_by_case(case_id, limit=500)
        stats = await self.get_graph_stats(case_id)
        return GraphResponse(
            case_id=case_id,
            nodes=[self._node(entity) for entity in entities],
            edges=[self._edge(relationship) for relationship in relationships],
            stats=stats,
        )

    async def get_entity_connections(
        self, entity_id: str,
    ) -> EntityConnectionsResponse | None:
        target = await self._ent_repo.get_by_id(entity_id)
        if not target:
            return None
        relationships = await self._rel_repo.list_by_entity(entity_id)
        neighbor_ids = {
            relationship.target_entity_id
            if relationship.source_entity_id == entity_id
            else relationship.source_entity_id
            for relationship in relationships
        }
        neighbors = []
        for neighbor_id in sorted(neighbor_ids):
            entity = await self._ent_repo.get_by_id(neighbor_id)
            if entity:
                neighbors.append(self._node(entity))
        return EntityConnectionsResponse(
            entity_id=target.id,
            entity_name=target.name,
            entity_type=target.entity_type.value,
            connections_count=len(neighbors),
            connected_nodes=neighbors,
            edges=[self._edge(relationship) for relationship in relationships],
        )

    async def get_entity_neighbors(
        self, entity_id: str, depth: int = 1,
    ) -> EntityNeighborsResponse | None:
        if not await self._ent_repo.get_by_id(entity_id):
            return None
        visited = {entity_id}
        relationships: dict[str, Any] = {}
        queue = deque([(entity_id, 0)])
        while queue:
            current, current_depth = queue.popleft()
            if current_depth >= depth:
                continue
            for relationship in await self._rel_repo.list_by_entity(current):
                relationships[relationship.id] = relationship
                neighbor = (
                    relationship.target_entity_id
                    if relationship.source_entity_id == current
                    else relationship.source_entity_id
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, current_depth + 1))
        nodes = []
        for node_id in sorted(visited):
            entity = await self._ent_repo.get_by_id(node_id)
            if entity:
                nodes.append(self._node(entity))
        return EntityNeighborsResponse(
            entity_id=entity_id,
            depth=depth,
            total_neighbors=max(0, len(nodes) - 1),
            nodes=nodes,
            edges=[self._edge(item) for item in relationships.values()],
        )

    async def get_graph_stats(self, case_id: str) -> GraphStats:
        entities, _ = await self._ent_repo.list_by_case(case_id, limit=500)
        relationships, _ = await self._rel_repo.list_by_case(case_id, limit=500)
        node_types: dict[str, int] = {}
        degree: dict[str, int] = {}
        relationship_types: dict[str, int] = {}
        for entity in entities:
            key = entity.entity_type.value
            node_types[key] = node_types.get(key, 0) + 1
        for relationship in relationships:
            key = relationship.relationship_type.value
            relationship_types[key] = relationship_types.get(key, 0) + 1
            degree[relationship.source_entity_id] = degree.get(relationship.source_entity_id, 0) + 1
            degree[relationship.target_entity_id] = degree.get(relationship.target_entity_id, 0) + 1
        top_connected = []
        for entity_id, count in sorted(degree.items(), key=lambda item: (-item[1], item[0]))[:5]:
            entity = await self._ent_repo.get_by_id(entity_id)
            if entity:
                top_connected.append(
                    {"id": entity.id, "name": entity.name, "type": entity.entity_type.value, "degree": count}
                )
        node_count = len(entities)
        edge_count = len(relationships)
        density = (
            (2 * edge_count) / (node_count * (node_count - 1))
            if node_count > 1
            else 0.0
        )
        return GraphStats(
            total_nodes=node_count,
            total_edges=edge_count,
            density=round(density, 4),
            node_types_breakdown=node_types,
            relationship_types_breakdown=relationship_types,
            top_connected_entities=top_connected,
        )

    async def get_case_linkage(self, case_id: str) -> dict[str, Any]:
        remote = await self._request("GET", f"/linkage/{case_id}")
        if remote is not None:
            return remote
        if not hasattr(self._ent_repo, "_entities"):
            from fastapi import HTTPException

            raise HTTPException(status_code=503, detail="Case linkage unavailable; graph service could not be reached.")
        records = list(self._ent_repo._entities.values())
        own = {
            (item["entity_type"].value, item["name"].strip().casefold())
            for item in records
            if item["case_id"] == case_id
        }
        grouped: dict[str, list[dict[str, str]]] = {}
        for item in records:
            other_case = item["case_id"]
            key = (item["entity_type"].value, item["name"].strip().casefold())
            if other_case != case_id and key in own:
                grouped.setdefault(other_case, []).append(
                    {"entity_type": key[0], "value": item["name"]}
                )
        return {
            "case_id": case_id,
            "linked_cases": [
                {
                    "case_id": linked_case,
                    "shared_entities": shared,
                    "link_strength": round(min(0.99, 0.45 + 0.2 * len(shared)), 2),
                    "explanation": (
                        f"Cases share {len(shared)} normalized entity signal(s): "
                        + ", ".join(f"{item['entity_type']} {item['value']}" for item in shared)
                    ),
                }
                for linked_case, shared in sorted(grouped.items())
            ],
            "source": "case_api_fallback",
        }

    async def get_shortest_path(
        self, source_entity_id: str, target_entity_id: str,
    ) -> ShortestPathResponse:
        source = await self._ent_repo.get_by_id(source_entity_id)
        target = await self._ent_repo.get_by_id(target_entity_id)
        if not source or not target:
            return ShortestPathResponse(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                path_found=False,
                message="Source or target entity not found.",
            )
        queue = deque([[source_entity_id]])
        visited = {source_entity_id}
        path: list[str] | None = None
        while queue:
            candidate = queue.popleft()
            current = candidate[-1]
            if current == target_entity_id:
                path = candidate
                break
            for relationship in await self._rel_repo.list_by_entity(current):
                neighbor = (
                    relationship.target_entity_id
                    if relationship.source_entity_id == current
                    else relationship.source_entity_id
                )
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append([*candidate, neighbor])
        if path is None:
            return ShortestPathResponse(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                path_found=False,
                message="No path exists between the selected entities.",
            )
        nodes = []
        edges = []
        for node_id in path:
            entity = await self._ent_repo.get_by_id(node_id)
            if entity:
                nodes.append(self._node(entity))
        for left, right in pairwise(path):
            for relationship in await self._rel_repo.list_by_entity(left):
                if {relationship.source_entity_id, relationship.target_entity_id} == {left, right}:
                    edges.append(self._edge(relationship))
                    break
        return ShortestPathResponse(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            path_found=True,
            hop_count=len(path) - 1,
            nodes=nodes,
            edges=edges,
            message=f"Shortest evidence path contains {len(path) - 1} hop(s).",
        )


graph_service_integration = IntegratedGraphService()
