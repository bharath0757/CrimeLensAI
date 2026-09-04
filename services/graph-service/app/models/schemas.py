from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict, field_validator, AliasChoices
from app.models import EntityType

ALLOWED_RELATIONSHIP_TYPES = {
    "USES", "OWNS", "LOCATED_AT", "WORKS_FOR", "CONTACTED", 
    "TRANSACTED", "CO_LOCATED", "RELATED", "ASSOCIATED", 
    "USED_PHONE", "CO_OCCURS"
}

class EntityUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    case_id: str = Field(min_length=1)
    entity_id: Optional[str] = Field(default=None, validation_alias=AliasChoices('entity_id', 'id'))
    entity_type: EntityType
    value: str = Field(min_length=1)
    normalized_value: Optional[str] = Field(default=None, validation_alias=AliasChoices('normalized_value', 'canonical_value'))
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source_field: str = "unknown"
    start_offset: Optional[int] = Field(default=None, ge=0)
    end_offset: Optional[int] = Field(default=None, ge=0)

class EntityUpsertResponse(BaseModel):
    status: str
    entity_id: str
    entity_type: str
    canonical_value: str
    created: bool
    case_ids: List[str]
    explanation: str

class RelationshipCreateRequest(BaseModel):
    source_entity_id: str = Field(min_length=1)
    target_entity_id: str = Field(min_length=1)
    relationship_type: str = Field(min_length=1)
    source_case_id: str = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    why_linked: str = Field(min_length=1)
    evidence_record_id: Optional[str] = None
    
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
    shared_entities: List[SharedEntity]
    link_strength: float
    explanation: str

class LinkageResponse(BaseModel):
    case_id: str
    linked_cases: List[LinkedCase]

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
    members: List[CommunityMember]
    case_ids: List[str]
    size: int
    summary: str

class CommunityResponse(BaseModel):
    communities: List[Community]
    method: str
    total_communities: int

class PathStep(BaseModel):
    source: str
    target: str
    source_label: str = ""
    target_label: str = ""
    relationship_type: Optional[str] = None
    confidence: Optional[float] = None

class ShortestPathResponse(BaseModel):
    entity_a: str
    entity_b: str
    path: List[str]
    steps: List[PathStep]
    path_length: int
    explanation: str

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    neo4j: str
    backend: str
