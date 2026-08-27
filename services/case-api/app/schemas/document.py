from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProcessingStatus(str, Enum):
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
    file_path: Optional[str] = None
    processing_status: ProcessingStatus
    extracted_entity_count: int = 0
    extracted_relationship_count: int = 0
    uploaded_by: str
    created_at: datetime
    updated_at: datetime
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    total: int
    items: List[DocumentResponse]


class DocumentProcessingStatusResponse(BaseModel):
    document_id: str
    case_id: str
    processing_status: ProcessingStatus
    progress_percentage: float = 0.0
    extracted_entity_count: int = 0
    extracted_relationship_count: int = 0
    message: str = "Status retrieved"
    details: Optional[Dict[str, Any]] = None
