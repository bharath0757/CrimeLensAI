from typing import Any

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str
    type: str
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = 1.0


class GraphStats(BaseModel):
    total_nodes: int = 0
    total_edges: int = 0
    density: float = 0.0
    node_types_breakdown: dict[str, int] = Field(default_factory=dict)
    relationship_types_breakdown: dict[str, int] = Field(default_factory=dict)
    top_connected_entities: list[dict[str, Any]] = Field(default_factory=list)


class GraphResponse(BaseModel):
    case_id: str
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    stats: GraphStats


class EntityConnectionsResponse(BaseModel):
    entity_id: str
    entity_name: str
    entity_type: str
    connections_count: int
    connected_nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class EntityNeighborsResponse(BaseModel):
    entity_id: str
    depth: int = 1
    total_neighbors: int
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)


class ShortestPathResponse(BaseModel):
    source_entity_id: str
    target_entity_id: str
    path_found: bool
    hop_count: int = 0
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    message: str = "Path evaluation completed"


class SharedLinkEntity(BaseModel):
    entity_id: str | None = None
    entity_type: str
    value: str
    canonical_value: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    is_masked: bool = False


class LinkScoreComponents(BaseModel):
    entity_overlap: float = Field(ge=0, le=1)
    phone_overlap: float = Field(ge=0, le=1)
    transaction_overlap: float = Field(ge=0, le=1)
    location_overlap: float = Field(ge=0, le=1)
    semantic_similarity: float = Field(ge=0, le=1)


class LinkedCase(BaseModel):
    case_id: str
    shared_entities: list[SharedLinkEntity]
    link_strength: float = Field(ge=0, le=1)
    explanation: str
    score_components: LinkScoreComponents | None = None


class CaseLinkageResponse(BaseModel):
    case_id: str
    linked_cases: list[LinkedCase]
    source: str = "graph"
