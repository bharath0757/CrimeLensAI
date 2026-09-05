from pydantic import BaseModel, Field

from app.schemas.case import CaseResponse
from app.schemas.document import DocumentResponse
from app.schemas.entity import EntityResponse
from app.schemas.relationship import RelationshipResponse


class SearchQuery(BaseModel):
    q: str = Field(..., min_length=1, description="Search term or query string")
    case_id: str | None = None
    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=200)


class SearchCasesResponse(BaseModel):
    query: str
    total: int
    items: list[CaseResponse]


class SearchEntitiesResponse(BaseModel):
    query: str
    total: int
    items: list[EntityResponse]


class SearchDocumentsResponse(BaseModel):
    query: str
    total: int
    items: list[DocumentResponse]


class SearchRelationshipsResponse(BaseModel):
    query: str
    total: int
    items: list[RelationshipResponse]


class GlobalSearchResult(BaseModel):
    cases: list[CaseResponse] = Field(default_factory=list)
    entities: list[EntityResponse] = Field(default_factory=list)
    documents: list[DocumentResponse] = Field(default_factory=list)
    relationships: list[RelationshipResponse] = Field(default_factory=list)


class GlobalSearchResponse(BaseModel):
    query: str
    total_matches: int
    results: GlobalSearchResult
