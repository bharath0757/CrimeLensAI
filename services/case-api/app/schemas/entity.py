from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class EntityType(StrEnum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    EVENT = "EVENT"
    PHONE_NUMBER = "PHONE_NUMBER"
    EMAIL = "EMAIL"
    BANK_ACCOUNT = "BANK_ACCOUNT"
    BANK = "BANK"
    UPI_ID = "UPI_ID"
    AADHAAR = "AADHAAR"
    PAN = "PAN"
    PASSPORT = "PASSPORT"
    DATE = "DATE"
    IPC_SECTION = "IPC_SECTION"
    VEHICLE = "VEHICLE"
    OTHER = "OTHER"


class EntityBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    entity_type: EntityType
    description: str | None = None
    properties: dict[str, Any] = Field(default_factory=dict)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)

    @field_validator("properties")
    @classmethod
    def validate_occurrences(cls, value):
        if "occurrences" in value and (
            not isinstance(value["occurrences"], list)
            or any(not isinstance(item, dict) for item in value["occurrences"])
        ):
            raise ValueError("occurrences must be a list of source-reference objects")
        return value


class EntityCreate(EntityBase):
    source_document_id: str | None = None


class EntityUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    entity_type: EntityType | None = None
    description: str | None = None
    properties: dict[str, Any] | None = None
    confidence_score: float | None = Field(None, ge=0.0, le=1.0)


class EntityResponse(EntityBase):
    id: str
    case_id: str
    source_document_id: str | None = None
    created_at: datetime
    updated_at: datetime
    review_status: str = "PENDING"
    is_masked: bool = False

    model_config = ConfigDict(from_attributes=True)


class UnmaskRequest(BaseModel):
    reason: str = Field(..., min_length=10, max_length=500)


class EntityListResponse(BaseModel):
    total: int
    items: list[EntityResponse]
