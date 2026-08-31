from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0


class GraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    density: float = 0.0
    node_types_breakdown: Dict[str, int] = Field(default_factory=dict)
    relationship_types_breakdown: Dict[str, int] = Field(default_factory=dict)
    top_connected_entities: List[Dict[str, Any]] = Field(default_factory=list)


class GraphResponse(BaseModel):
    case_id: str
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    stats: GraphStats


class EntityConnectionsResponse(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    connections_count: int
    connected_nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class EntityNeighborsResponse(BaseModel):
    entity_id: str
    depth: int = 1
    total_neighbors: int
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)


class ShortestPathResponse(BaseModel):
    source_entity_id: str
    target_entity_id: str
    path_found: bool
    hop_count: int = 0
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    message: str = "Path evaluation completed"
