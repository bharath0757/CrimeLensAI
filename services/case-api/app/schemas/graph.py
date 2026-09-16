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


class CentralityMetrics(BaseModel):
    degree: float = Field(ge=0.0)
    betweenness: float = Field(ge=0.0)
    pagerank: float = Field(ge=0.0)


class CentralityResponse(BaseModel):
    entity_id: str
    centrality: CentralityMetrics
    explanation: str


class CasePattern(BaseModel):
    pattern_type: str
    case_ids: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    supporting_entity_ids: list[str] = Field(default_factory=list)
    explanation: str
    disposition: str = "INVESTIGATIVE_LEAD_NOT_FACT"


class CasePatternsResponse(BaseModel):
    case_id: str
    patterns: list[CasePattern] = Field(default_factory=list)


class LinkCandidate(BaseModel):
    source_entity_id: str
    target_entity_id: str
    source_name: str | None = None
    target_name: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    common_neighbor_ids: list[str] = Field(default_factory=list)
    explanation: str
    method: str | None = None
    disposition: str = "INVESTIGATIVE_LEAD_NOT_FACT"


class LinkPredictionsResponse(BaseModel):
    predictions: list[LinkCandidate] = Field(default_factory=list)


class InfluentialPerson(BaseModel):
    entity_id: str
    name: str
    entity_type: str = "PERSON"
    centrality: CentralityMetrics
    explanation: str
    is_masked: bool = False


class CaseInsightsResponse(BaseModel):
    case_id: str
    patterns: list[CasePattern] = Field(default_factory=list)
    influential_people: list[InfluentialPerson] = Field(default_factory=list)
    link_candidates: list[LinkCandidate] = Field(default_factory=list)
    status: str = "complete"
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Network analytics are investigative leads, not findings of identity, involvement, or guilt. "
        "Review the underlying source evidence before taking action."
    )
