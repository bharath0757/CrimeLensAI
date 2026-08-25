"""
CrimeLensAI — Shared Python Schemas
=====================================
Pydantic models shared across all Python backend services.

These models define the API contract. The TypeScript equivalents
in /packages/shared-types/typescript/types.ts MUST stay in sync
with these definitions.

Entity types, API request/response shapes, and common enums live here
so that extraction, graph, ledger, and api services all use the
same data structures without duplicating schema definitions.
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# Enums
# ============================================================

class EntityType(str, Enum):
    """Types of entities extracted from case data."""
    PERSON = "PERSON"
    PHONE = "PHONE"
    VEHICLE = "VEHICLE"
    UPI_ID = "UPI_ID"
    LOCATION = "LOCATION"
    ORG = "ORG"


class UserRole(str, Enum):
    """Role-based access control roles."""
    INVESTIGATOR = "INVESTIGATOR"
    SUPERVISOR = "SUPERVISOR"
    ADMIN = "ADMIN"


class CaseStatus(str, Enum):
    """Lifecycle status of a case."""
    DRAFT = "DRAFT"
    PROCESSING = "PROCESSING"
    ACTIVE = "ACTIVE"
    CLOSED = "CLOSED"
    ARCHIVED = "ARCHIVED"


# ============================================================
# Entity Models
# ============================================================

class ExtractedEntity(BaseModel):
    """An entity extracted from case text by the extraction service."""
    id: Optional[str] = None
    entity_type: EntityType
    value: str
    confidence: float = Field(ge=0.0, le=1.0, description="Extraction confidence score")
    start_offset: int = Field(ge=0, description="Character start position in source text")
    end_offset: int = Field(ge=0, description="Character end position in source text")
    source_field: str = Field(description="Which input field the entity was found in")
    case_id: Optional[str] = None
    confirmed: Optional[bool] = None  # None = pending review


class EntityResolutionGroup(BaseModel):
    """A group of entities resolved as the same real-world entity."""
    canonical_value: str
    entity_type: EntityType
    variants: list[ExtractedEntity]
    merge_confidence: float = Field(ge=0.0, le=1.0)


# ============================================================
# Case Models
# ============================================================

class CaseCreate(BaseModel):
    """Request body for creating a new case."""
    title: str
    fir_text: Optional[str] = None
    call_records: Optional[str] = None
    financial_logs: Optional[str] = None
    location_data: Optional[str] = None
    district: Optional[str] = None
    station: Optional[str] = None
    filing_date: Optional[datetime] = None


class CaseResponse(BaseModel):
    """Response body for a case."""
    id: str
    title: str
    status: CaseStatus
    district: Optional[str] = None
    station: Optional[str] = None
    filing_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    entities: list[ExtractedEntity] = []
    linked_case_count: int = 0


# ============================================================
# Graph Models
# ============================================================

class GraphRelationship(BaseModel):
    """A relationship between two entities in the graph."""
    id: Optional[str] = None
    source_entity_id: str
    target_entity_id: str
    relationship_type: str
    source_case_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    why_linked: str = Field(description="Human-readable explanation of why these entities are linked")


class CrossCaseLink(BaseModel):
    """A discovered link between two cases through shared entities."""
    case_a_id: str
    case_b_id: str
    shared_entities: list[ExtractedEntity]
    link_strength: float = Field(ge=0.0, le=1.0)
    explanation: str


# ============================================================
# Ledger Models
# ============================================================

class LedgerRecord(BaseModel):
    """A single entry in the tamper-evident hash-chain ledger."""
    id: Optional[str] = None
    timestamp: datetime
    action: str  # e.g., "ENTITY_CREATED", "RELATIONSHIP_ADDED", "ENTITY_CONFIRMED"
    actor_id: str  # User who triggered the action
    resource_type: str  # e.g., "entity", "relationship", "case"
    resource_id: str
    data_hash: str  # SHA-256 hash of the canonical record data
    previous_hash: Optional[str] = None  # Hash of the preceding record (chain link)
    chain_position: int


class LedgerVerification(BaseModel):
    """Result of verifying a ledger record's integrity."""
    record_id: str
    verified: bool
    computed_hash: str
    stored_hash: str
    chain_intact: bool
    message: str


# ============================================================
# Auth Models
# ============================================================

class UserProfile(BaseModel):
    """User profile returned after authentication."""
    id: str
    username: str
    full_name: str
    role: UserRole
    district: Optional[str] = None
    station: Optional[str] = None


class LoginRequest(BaseModel):
    """Login request body."""
    username: str
    password: str


class LoginResponse(BaseModel):
    """Login response with JWT token."""
    token: str
    token_type: str = "bearer"
    user: UserProfile


# ============================================================
# Dashboard Models
# ============================================================

class DashboardStats(BaseModel):
    """Aggregated statistics for the investigator dashboard."""
    total_cases: int = 0
    total_entities: int = 0
    cross_case_links: int = 0
    pending_reviews: int = 0
    cases_by_status: dict[str, int] = {}
    recent_links: list[CrossCaseLink] = []
