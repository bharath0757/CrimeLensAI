from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict


class ProcessingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class DocumentResponse(BaseModel):
    id: str
    case_id: str
    filename: str
    original_filename: str
    file_type: str
    file_size_bytes: int
    file_path: str | None = None
    processing_status: ProcessingStatus
    extracted_entity_count: int = 0
    extracted_relationship_count: int = 0
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    total: int
    items: list[DocumentResponse]


class DocumentProcessingStatusResponse(BaseModel):
    document_id: str
    case_id: str
    processing_status: ProcessingStatus
    progress_percentage: float = 0.0
    extracted_entity_count: int = 0
    extracted_relationship_count: int = 0
    message: str = "Status retrieved"
    details: dict[str, Any] | None = None
