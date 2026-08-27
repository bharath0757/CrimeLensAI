from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field
from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.entity import EntityResponse
from app.schemas.relationship import RelationshipResponse


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, description="Search term or query string")
    case_id: Optional[str] = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class SearchCasesResponse(BaseModel):
    query: str
    total: int
    items: List[CaseResponse]


class SearchEntitiesResponse(BaseModel):
    query: str
    total: int
    items: List[EntityResponse]


class SearchDocumentsResponse(BaseModel):
    query: str
    total: int
    items: List[DocumentResponse]


class SearchRelationshipsResponse(BaseModel):
    query: str
    total: int
    items: List[RelationshipResponse]


class GlobalSearchResult(BaseModel):
    cases: List[CaseResponse] = Field(default_factory=list)
    entities: List[EntityResponse] = Field(default_factory=list)
    documents: List[DocumentResponse] = Field(default_factory=list)
    relationships: List[RelationshipResponse] = Field(default_factory=list)


class GlobalSearchResponse(BaseModel):
    query: str
    total_matches: int
    results: GlobalSearchResult
