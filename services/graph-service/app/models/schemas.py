from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from app.models import EntityType
from app.models.evidence import RelationshipEvidence

ALLOWED_RELATIONSHIP_TYPES = {
    "USES", "OWNS", "LOCATED_AT", "WORKS_FOR", "CONTACTED", 
    "TRANSACTED", "CO_LOCATED", "RELATED", "ASSOCIATED", 
    "USED_PHONE", "CO_OCCURS", "CALLED", "TRANSFERRED_TO",
    "INVOLVED_IN", "COMMUNICATED_WITH", "TRANSFERRED_FUNDS",
    "HAS_ACCOUNT", "REGISTERED_TO"
}

class EntityUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    case_id: str = Field(min_length=1)
    entity_id: str | None = Field(default=None, validation_alias=AliasChoices('entity_id', 'id'))
    entity_type: EntityType
    value: str = Field(min_length=1)
    normalized_value: str | None = Field(default=None, validation_alias=AliasChoices('normalized_value', 'canonical_value'))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_field: str = "unknown"
    start_offset: int | None = Field(default=None, ge=0)
    end_offset: int | None = Field(default=None, ge=0)

class EntityUpsertResponse(BaseModel):
    status: str
    entity_id: str
    entity_type: str
    canonical_value: str
    created: bool
    case_ids: list[str]
    explanation: str

class RelationshipCreateRequest(BaseModel):
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    source_case_id: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    why_linked: str = Field(min_length=1)
    evidence_record_id: str | None = None
    evidence: RelationshipEvidence | None = None
    
    @field_validator('relationship_type')
    @classmethod
    def validate_relationship_type(cls, v: str) -> str:
        upper_v = v.upper()
        if upper_v not in ALLOWED_RELATIONSHIP_TYPES:
            raise ValueError(f"relationship_type must be one of {ALLOWED_RELATIONSHIP_TYPES}")
        return upper_v

class RelationshipCreateResponse(BaseModel):
    status: str
    relationship_id: str
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    explanation: str

class SharedEntity(BaseModel):
    entity_id: str
    entity_type: str
    value: str
    canonical_value: str
    confidence: float

class LinkedCase(BaseModel):
    case_id: str
    shared_entities: list[SharedEntity]
    link_strength: float
    explanation: str

class LinkageResponse(BaseModel):
    case_id: str
    linked_cases: list[LinkedCase]

class CentralityMetrics(BaseModel):
    degree: float
    betweenness: float
    pagerank: float

class CentralityResponse(BaseModel):
    entity_id: str
    centrality: CentralityMetrics
    explanation: str

class CommunityMember(BaseModel):
    entity_id: str
    entity_type: str
    value: str

class Community(BaseModel):
    community_id: int
    members: list[CommunityMember]
    case_ids: list[str]
    size: int
    summary: str

class CommunityResponse(BaseModel):
    communities: list[Community]
    method: str
    total_communities: int

class PathStep(BaseModel):
    source: str
    target: str
    source_label: str = ""
    target_label: str = ""
    relationship_type: str | None = None
    confidence: float | None = None

class ShortestPathResponse(BaseModel):
    entity_a: str
    entity_b: str
    path: list[str]
    steps: list[PathStep]
    path_length: int
    explanation: str

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    neo4j: str
    backend: str
