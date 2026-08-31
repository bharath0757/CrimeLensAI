import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from app.schemas.document import DocumentResponse, ProcessingStatus


class DocumentRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, doc_id: str) -> Optional[DocumentResponse]:
        pass

    @abstractmethod
    async def list_by_case(self, case_id: str, skip: int = 0, limit: int = 50) -> Tuple[List[DocumentResponse], int]:
        pass

    @abstractmethod
    async def create(
        self,
        case_id: str,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        file_path: str,
        uploaded_by: str,
    ) -> DocumentResponse:
        pass

    @abstractmethod
    async def update_status(self, doc_id: str, status: ProcessingStatus, error_message: Optional[str] = None) -> Optional[DocumentResponse]:
        pass

    @abstractmethod
    async def update_extraction_counts(self, doc_id: str, entity_count: int, relationship_count: int):
        pass

    @abstractmethod
    async def delete(self, doc_id: str) -> Optional[str]:  # Returns file_path if deleted
        pass

    @abstractmethod
    async def search(self, query: str, case_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> Tuple[List[DocumentResponse], int]:
        pass

    @abstractmethod
    async def count(self, status: Optional[ProcessingStatus] = None) -> int:
        pass


class InMemoryDocumentRepository(DocumentRepositoryInterface):
    """In-memory Document Repository implementation."""

    def __init__(self):
        self._documents: Dict[str, Dict[str, Any]] = {}

    async def get_by_id(self, doc_id: str) -> Optional[DocumentResponse]:
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        return DocumentResponse(**doc)

    async def list_by_case(self, case_id: str, skip: int = 0, limit: int = 50) -> Tuple[List[DocumentResponse], int]:
        filtered = [d for d in self._documents.values() if d["case_id"] == case_id]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [DocumentResponse(**d) for d in paginated], total

    async def create(
        self,
        case_id: str,
        filename: str,
        original_filename: str,
        file_type: str,
        file_size_bytes: int,
        file_path: str,
        uploaded_by: str,
    ) -> DocumentResponse:
        doc_id = f"doc-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        doc_dict = {
            "id": doc_id,
            "case_id": case_id,
            "filename": filename,
            "original_filename": original_filename,
            "file_type": file_type,
            "file_size_bytes": file_size_bytes,
            "file_path": file_path,
            "processing_status": ProcessingStatus.PENDING,
            "extracted_entity_count": 0,
            "extracted_relationship_count": 0,
            "uploaded_by": uploaded_by,
            "created_at": now,
            "updated_at": now,
            "error_message": None,
        }
        self._documents[doc_id] = doc_dict
        return DocumentResponse(**doc_dict)

    async def update_status(self, doc_id: str, status: ProcessingStatus, error_message: Optional[str] = None) -> Optional[DocumentResponse]:
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        doc["processing_status"] = status
        if error_message:
            doc["error_message"] = error_message
        doc["updated_at"] = datetime.now(timezone.utc)
        return DocumentResponse(**doc)

    async def update_extraction_counts(self, doc_id: str, entity_count: int, relationship_count: int):
        doc = self._documents.get(doc_id)
        if doc:
            doc["extracted_entity_count"] += entity_count
            doc["extracted_relationship_count"] += relationship_count
            doc["updated_at"] = datetime.now(timezone.utc)

    async def delete(self, doc_id: str) -> Optional[str]:
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        file_path = doc["file_path"]
        del self._documents[doc_id]
        return file_path

    async def search(self, query: str, case_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> Tuple[List[DocumentResponse], int]:
        q = query.lower()
        filtered = list(self._documents.values())
        if case_id:
            filtered = [d for d in filtered if d["case_id"] == case_id]
        filtered = [
            d for d in filtered
            if q in d["original_filename"].lower() or q in d["file_type"].lower() or q in d["filename"].lower()
        ]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [DocumentResponse(**d) for d in paginated], total

    async def count(self, status: Optional[ProcessingStatus] = None) -> int:
        if not status:
            return len(self._documents)
        return sum(1 for d in self._documents.values() if d["processing_status"] == status)


document_repository = InMemoryDocumentRepository()
