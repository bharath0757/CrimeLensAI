import httpx
import os
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Set
from collections import deque

from app.schemas.graph import (
    GraphResponse,
    GraphNode,
    GraphEdge,
    GraphStats,
    EntityConnectionsResponse,
    EntityNeighborsResponse,
    ShortestPathResponse,
)
from app.repositories.entity_repo import entity_repository, EntityRepositoryInterface
from app.repositories.relationship_repo import relationship_repository, RelationshipRepositoryInterface


class GraphServiceInterface(ABC):
    @abstractmethod
    async def sync_entity(self, case_id: str, entity: Any) -> None:
        pass
    
    @abstractmethod
    async def sync_relationship(self, case_id: str, rel: Any) -> None:
        pass
    """Abstract interface contract for Graph & Network Analysis operations."""

    @abstractmethod
    async def get_case_graph(self, case_id: str) -> GraphResponse:
        """Fetch complete network topology payload for a case."""
        pass

    @abstractmethod
    async def get_entity_connections(self, entity_id: str) -> Optional[EntityConnectionsResponse]:
        """Get direct connections and edges for an entity."""
        pass

    @abstractmethod
    async def get_entity_neighbors(self, entity_id: str, depth: int = 1) -> Optional[EntityNeighborsResponse]:
        """Get k-hop neighborhood graph around an entity."""
        pass

    @abstractmethod
    async def get_graph_stats(self, case_id: str) -> GraphStats:
        """Get network analytics metrics for a case."""
        pass

    @abstractmethod
    async def get_shortest_path(self, source_entity_id: str, target_entity_id: str) -> ShortestPathResponse:
        """Calculate shortest network path between two entities."""
        pass


class MockGraphService(GraphServiceInterface):
    async def sync_entity(self, case_id: str, entity: Any) -> None: pass
    async def sync_relationship(self, case_id: str, rel: Any) -> None: pass
    """
    Graph Service implementation.
    Operates on entities and relationships stored in repositories to compute node-edge graph topologies,
    neighborhood subgraphs, and BFS shortest path algorithms.
    This allows frontend graph visualization to work seamlessly until the Graph teammate connects Neo4j.
    """

    def __init__(
        self,
        ent_repo: EntityRepositoryInterface = entity_repository,
        rel_repo: RelationshipRepositoryInterface = relationship_repository,
    ):
        self._ent_repo = ent_repo
        self._rel_repo = rel_repo

    async def get_case_graph(self, case_id: str) -> GraphResponse:
        entities, _ = await self._ent_repo.list_by_case(case_id, limit=500)
        relationships, _ = await self._rel_repo.list_by_case(case_id, limit=500)

        nodes = [
            GraphNode(
                id=e.id,
                label=e.name,
                type=e.entity_type.value,
                properties=e.properties,
                confidence_score=e.confidence_score,
            )
            for e in entities
        ]

        edges = [
            GraphEdge(
                id=r.id,
                source=r.source_entity_id,
                target=r.target_entity_id,
                label=r.relationship_type.value,
                type=r.relationship_type.value,
                properties=r.properties,
                confidence_score=r.confidence_score,
            )
            for r in relationships
        ]

        stats = await self.get_graph_stats(case_id)
        return GraphResponse(case_id=case_id, nodes=nodes, edges=edges, stats=stats)

    async def get_entity_connections(self, entity_id: str) -> Optional[EntityConnectionsResponse]:
        target_entity = await self._ent_repo.get_by_id(entity_id)
        if not target_entity:
            return None

        rels = await self._rel_repo.list_by_entity(entity_id)
        connected_ids: Set[str] = set()
        edges: List[GraphEdge] = []

        for r in rels:
            connected_ids.add(r.source_entity_id)
            connected_ids.add(r.target_entity_id)
            edges.append(
                GraphEdge(
                    id=r.id,
                    source=r.source_entity_id,
                    target=r.target_entity_id,
                    label=r.relationship_type.value,
                    type=r.relationship_type.value,
                    properties=r.properties,
                    confidence_score=r.confidence_score,
                )
            )

        connected_ids.discard(entity_id)
        connected_nodes: List[GraphNode] = []
        for cid in connected_ids:
            ent = await self._ent_repo.get_by_id(cid)
            if ent:
                connected_nodes.append(
                    GraphNode(
                        id=ent.id,
                        label=ent.name,
                        type=ent.entity_type.value,
                        properties=ent.properties,
                        confidence_score=ent.confidence_score,
                    )
                )

        return EntityConnectionsResponse(
            entity_id=target_entity.id,
            entity_name=target_entity.name,
            entity_type=target_entity.entity_type.value,
            connections_count=len(connected_nodes),
            connected_nodes=connected_nodes,
            edges=edges,
        )

    async def get_entity_neighbors(self, entity_id: str, depth: int = 1) -> Optional[EntityNeighborsResponse]:
        target_entity = await self._ent_repo.get_by_id(entity_id)
        if not target_entity:
            return None

        visited_nodes: Set[str] = {entity_id}
        collected_edges: List[GraphEdge] = []
        queue = deque([(entity_id, 0)])

        while queue:
            curr_id, curr_depth = queue.popleft()
            if curr_depth >= depth:
                continue

            rels = await self._rel_repo.list_by_entity(curr_id)
            for r in rels:
                edge_obj = GraphEdge(
                    id=r.id,
                    source=r.source_entity_id,
                    target=r.target_entity_id,
                    label=r.relationship_type.value,
                    type=r.relationship_type.value,
                    properties=r.properties,
                    confidence_score=r.confidence_score,
                )
                if edge_obj not in collected_edges:
                    collected_edges.append(edge_obj)

                next_id = r.target_entity_id if r.source_entity_id == curr_id else r.source_entity_id
                if next_id not in visited_nodes:
                    visited_nodes.add(next_id)
                    queue.append((next_id, curr_depth + 1))

        nodes: List[GraphNode] = []
        for nid in visited_nodes:
            ent = await self._ent_repo.get_by_id(nid)
            if ent:
                nodes.append(
                    GraphNode(
                        id=ent.id,
                        label=ent.name,
                        type=ent.entity_type.value,
                        properties=ent.properties,
                        confidence_score=ent.confidence_score,
                    )
                )

        return EntityNeighborsResponse(
            entity_id=entity_id,
            depth=depth,
            total_neighbors=len(nodes) - 1,
            nodes=nodes,
            edges=collected_edges,
        )

    async def get_graph_stats(self, case_id: str) -> GraphStats:
        entities, _ = await self._ent_repo.list_by_case(case_id, limit=500)
        relationships, _ = await self._rel_repo.list_by_case(case_id, limit=500)

        n_count = len(entities)
        e_count = len(relationships)

        density = (2 * e_count) / (n_count * (n_count - 1)) if n_count > 1 else 0.0

        node_types: Dict[str, int] = {}
        for e in entities:
            t = e.entity_type.value
            node_types[t] = node_types.get(t, 0) + 1

        rel_types: Dict[str, int] = {}
        degree_map: Dict[str, int] = {}
        for r in relationships:
            t = r.relationship_type.value
            rel_types[t] = rel_types.get(t, 0) + 1
            degree_map[r.source_entity_id] = degree_map.get(r.source_entity_id, 0) + 1
            degree_map[r.target_entity_id] = degree_map.get(r.target_entity_id, 0) + 1

        top_entities: List[Dict[str, Any]] = []
        sorted_degrees = sorted(degree_map.items(), key=lambda x: x[1], reverse=True)[:5]
        for ent_id, deg in sorted_degrees:
            ent = await self._ent_repo.get_by_id(ent_id)
            if ent:
                top_entities.append({"id": ent.id, "name": ent.name, "type": ent.entity_type.value, "degree": deg})

        return GraphStats(
            total_nodes=n_count,
            total_edges=e_count,
            density=round(density, 4),
            node_types_breakdown=node_types,
            relationship_types_breakdown=rel_types,
            top_connected_entities=top_entities,
        )

    async def get_shortest_path(self, source_entity_id: str, target_entity_id: str) -> ShortestPathResponse:
        src = await self._ent_repo.get_by_id(source_entity_id)
        tgt = await self._ent_repo.get_by_id(target_entity_id)
        if not src or not tgt:
            return ShortestPathResponse(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                path_found=False,
                message="Source or target entity not found.",
            )

        if source_entity_id == target_entity_id:
            return ShortestPathResponse(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                path_found=True,
                hop_count=0,
                nodes=[
                    GraphNode(
                        id=src.id,
                        label=src.name,
                        type=src.entity_type.value,
                        properties=src.properties,
                        confidence_score=src.confidence_score,
                    )
                ],
                edges=[],
                message="Source and target are the same node.",
            )

        # BFS for shortest path
        queue = deque([[source_entity_id]])
        visited = {source_entity_id}
        found_path: Optional[List[str]] = None

        while queue:
            path = queue.popleft()
            curr_node = path[-1]

            if curr_node == target_entity_id:
                found_path = path
                break

            rels = await self._rel_repo.list_by_entity(curr_node)
            for r in rels:
                next_node = r.target_entity_id if r.source_entity_id == curr_node else r.source_entity_id
                if next_node not in visited:
                    visited.add(next_node)
                    new_path = list(path)
                    new_path.append(next_node)
                    queue.append(new_path)

        if not found_path:
            return ShortestPathResponse(
                source_entity_id=source_entity_id,
                target_entity_id=target_entity_id,
                path_found=False,
                message="No path exists between the specified entities in the network.",
            )

        # Reconstruct path nodes and edges
        path_nodes: List[GraphNode] = []
        for nid in found_path:
            ent = await self._ent_repo.get_by_id(nid)
            if ent:
                path_nodes.append(
                    GraphNode(
                        id=ent.id,
                        label=ent.name,
                        type=ent.entity_type.value,
                        properties=ent.properties,
                        confidence_score=ent.confidence_score,
                    )
                )

        path_edges: List[GraphEdge] = []
        for i in range(len(found_path) - 1):
            u, v = found_path[i], found_path[i + 1]
            u_rels = await self._rel_repo.list_by_entity(u)
            for r in u_rels:
                if (r.source_entity_id == u and r.target_entity_id == v) or (r.source_entity_id == v and r.target_entity_id == u):
                    path_edges.append(
                        GraphEdge(
                            id=r.id,
                            source=r.source_entity_id,
                            target=r.target_entity_id,
                            label=r.relationship_type.value,
                            type=r.relationship_type.value,
                            properties=r.properties,
                            confidence_score=r.confidence_score,
                        )
                    )
                    break

        return ShortestPathResponse(
            source_entity_id=source_entity_id,
            target_entity_id=target_entity_id,
            path_found=True,
            hop_count=len(found_path) - 1,
            nodes=path_nodes,
            edges=path_edges,
            message=f"Shortest path found with {len(found_path) - 1} hops.",
        )


class HttpGraphService(GraphServiceInterface):
    def __init__(self, base_url: str = "http://graph:8002/api/v1"):
        self.base_url = base_url
    
    async def sync_entity(self, case_id: str, entity: Any) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.base_url}/entities", json={"case_id": case_id, "entity": {"name": entity.name, "entity_type": entity.entity_type.value}})
            
    async def sync_relationship(self, case_id: str, rel: Any) -> None:
        async with httpx.AsyncClient() as client:
            src_ent = await entity_repository.get_by_id(rel.source_entity_id)
            tgt_ent = await entity_repository.get_by_id(rel.target_entity_id)
            await client.post(f"{self.base_url}/relationships", json={
                "case_id": case_id, 
                "relationship": {
                    "source_entity_name": src_ent.name,
                    "source_entity_type": src_ent.entity_type.value,
                    "target_entity_name": tgt_ent.name,
                    "target_entity_type": tgt_ent.entity_type.value,
                    "relationship_type": rel.relationship_type.value,
                    "properties": rel.properties,
                    "confidence_score": rel.confidence_score,
                    "description": rel.description
                }
            })

    async def get_case_graph(self, case_id: str) -> GraphResponse:
        pass # Not required for Neo4j tests unless specified

    async def get_entity_connections(self, entity_id: str) -> Optional[EntityConnectionsResponse]:
        pass

    async def get_entity_neighbors(self, entity_id: str, depth: int = 1) -> Optional[EntityNeighborsResponse]:
        pass

    async def get_graph_stats(self, case_id: str) -> GraphStats:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/stats/{case_id}")
            if r.status_code == 200:
                data = r.json()
                return GraphStats(
                    total_nodes=data.get("total_nodes", 0),
                    total_edges=data.get("total_edges", 0),
                    density=data.get("density", 0.0),
                    node_types_breakdown=data.get("node_types_breakdown", {}),
                    relationship_types_breakdown=data.get("relationship_types_breakdown", {}),
                    top_connected_entities=data.get("top_connected_entities", [])
                )
            return None

    async def get_shortest_path(self, source_entity_id: str, target_entity_id: str) -> ShortestPathResponse:
        src_ent = await entity_repository.get_by_id(source_entity_id)
        tgt_ent = await entity_repository.get_by_id(target_entity_id)
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{self.base_url}/shortest-path", params={"entity_a": src_ent.name, "entity_b": tgt_ent.name})
            if r.status_code == 200:
                data = r.json()
                return ShortestPathResponse(
                    source_entity_id=source_entity_id,
                    target_entity_id=target_entity_id,
                    path_found=data["path_found"],
                    hop_count=len(data.get("path_edges", [])),
                    nodes=[],
                    edges=[],
                    message=data.get("explanation", "")
                )
            return None
            
graph_service_integration = HttpGraphService(base_url=os.getenv("GRAPH_SERVICE_URL", "http://graph:8002").rstrip("/") + "/api/v1")






