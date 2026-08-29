"""
Entity schemas for the Case API.
Mirrors the ExtractedEntity from contracts/python/schemas.py.
"""

from typing import Optional

from pydantic import BaseModel, Field


class ExtractedEntity(BaseModel):
    """An entity extracted from case text by the extraction service."""
    id: Optional[str] = None
    entity_type: str
    value: str
    confidence: float = Field(ge=0.0, le=1.0)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    source_field: str = "text"
    case_id: Optional[str] = None
    confirmed: Optional[bool] = None
