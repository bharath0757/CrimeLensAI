import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from app.schemas.case import CaseResponse, CaseCreate, CaseUpdate, CaseStatus, CasePriority


class CaseRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, case_id: str) -> Optional[CaseResponse]:
        pass

    @abstractmethod
    async def get_by_number(self, case_number: str) -> Optional[CaseResponse]:
        pass

    @abstractmethod
    async def list_cases(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[CaseStatus] = None,
        priority: Optional[CasePriority] = None,
        owner_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[CaseResponse], int]:
        pass

    @abstractmethod
    async def create(self, case_create: CaseCreate, owner_id: str) -> CaseResponse:
        pass

    @abstractmethod
    async def update(self, case_id: str, case_update: CaseUpdate) -> Optional[CaseResponse]:
        pass

    @abstractmethod
    async def update_counts(self, case_id: str, doc_delta: int = 0, entity_delta: int = 0, rel_delta: int = 0):
        pass

    @abstractmethod
    async def delete(self, case_id: str) -> bool:
        pass

    @abstractmethod
    async def count(self, status: Optional[CaseStatus] = None) -> int:
        pass


class InMemoryCaseRepository(CaseRepositoryInterface):
    """In-memory Case Repository implementation."""

    def __init__(self):
        self._cases: Dict[str, Dict[str, Any]] = {}
        self._case_counter = 100
        self._seed_sample_case()

    def _seed_sample_case(self):
        case_id_1 = "case-sample-001"
        self._cases[case_id_1] = {
            "id": case_id_1,
            "case_number": "CASE-2026-001",
            "title": "Operation CyberLabyrinth Fraud Ring",
            "description": "Investigation into multi-jurisdictional financial fraud and identity theft syndicate.",
            "status": CaseStatus.OPEN,
            "priority": CasePriority.HIGH,
            "owner_id": "user-inv-002",
            "assigned_investigator_ids": ["user-inv-002", "user-admin-001"],
            "tags": ["fraud", "cybercrime", "wire-transfer"],
            "document_count": 2,
            "entity_count": 3,
            "relationship_count": 2,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

        case_id_2 = "case-sample-002"
        self._cases[case_id_2] = {
            "id": case_id_2,
            "case_number": "CASE-2026-002",
            "title": "Lucknow Hawala Money Syndicate",
            "description": "Cross-border illicit money transfer network linked to suspicious phone numbers.",
            "status": CaseStatus.IN_PROGRESS,
            "priority": CasePriority.CRITICAL,
            "owner_id": "user-admin-001",
            "assigned_investigator_ids": ["user-admin-001"],
            "tags": ["hawala", "financial_fraud", "lucknow"],
            "document_count": 1,
            "entity_count": 3,
            "relationship_count": 1,
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }

    async def get_by_id(self, case_id: str) -> Optional[CaseResponse]:
        c = self._cases.get(case_id)
        if not c:
            return None
        return CaseResponse(**c)

    async def get_by_number(self, case_number: str) -> Optional[CaseResponse]:
        for c in self._cases.values():
            if c["case_number"].lower() == case_number.lower():
                return CaseResponse(**c)
        return None

    async def list_cases(
        self,
        skip: int = 0,
        limit: int = 50,
        status: Optional[CaseStatus] = None,
        priority: Optional[CasePriority] = None,
        owner_id: Optional[str] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[CaseResponse], int]:
        filtered = list(self._cases.values())

        if status:
            filtered = [c for c in filtered if c["status"] == status]
        if priority:
            filtered = [c for c in filtered if c["priority"] == priority]
        if owner_id:
            filtered = [c for c in filtered if c["owner_id"] == owner_id or owner_id in c.get("assigned_investigator_ids", [])]
        if search_query:
            q = search_query.lower()
            filtered = [
                c for c in filtered
                if q in c["title"].lower() or q in c["description"].lower() or q in c["case_number"].lower() or any(q in t.lower() for t in c.get("tags", []))
            ]

        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [CaseResponse(**c) for c in paginated], total

    async def create(self, case_create: CaseCreate, owner_id: str) -> CaseResponse:
        case_id = f"case-{uuid.uuid4().hex[:8]}"
        self._case_counter += 1
        case_number = case_create.case_number or f"CASE-2026-{self._case_counter:03d}"
        now = datetime.now(timezone.utc)

        assigned_ids = list(set(case_create.assigned_investigator_ids + [owner_id]))

        c_dict = {
            "id": case_id,
            "case_number": case_number,
            "title": case_create.title,
            "description": case_create.description,
            "status": CaseStatus.OPEN,
            "priority": case_create.priority,
            "owner_id": owner_id,
            "assigned_investigator_ids": assigned_ids,
            "tags": case_create.tags,
            "document_count": 0,
            "entity_count": 0,
            "relationship_count": 0,
            "created_at": now,
            "updated_at": now,
        }
        self._cases[case_id] = c_dict
        return CaseResponse(**c_dict)

    async def update(self, case_id: str, case_update: CaseUpdate) -> Optional[CaseResponse]:
        c = self._cases.get(case_id)
        if not c:
            return None

        update_dict = case_update.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                c[k] = v
        c["updated_at"] = datetime.now(timezone.utc)
        return CaseResponse(**c)

    async def update_counts(self, case_id: str, doc_delta: int = 0, entity_delta: int = 0, rel_delta: int = 0):
        c = self._cases.get(case_id)
        if c:
            c["document_count"] = max(0, c.get("document_count", 0) + doc_delta)
            c["entity_count"] = max(0, c.get("entity_count", 0) + entity_delta)
            c["relationship_count"] = max(0, c.get("relationship_count", 0) + rel_delta)
            c["updated_at"] = datetime.now(timezone.utc)

    async def delete(self, case_id: str) -> bool:
        if case_id in self._cases:
            del self._cases[case_id]
            return True
        return False

    async def count(self, status: Optional[CaseStatus] = None) -> int:
        if not status:
            return len(self._cases)
        return sum(1 for c in self._cases.values() if c["status"] == status)


case_repository = InMemoryCaseRepository()
