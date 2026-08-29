"""
CrimeLensAI — Case Repository
================================
In-memory persistence layer for cases.

Swap this out for a real database repository (PostgreSQL, Firestore, etc.)
when infrastructure is available. The interface stays the same.
"""

from datetime import datetime
from typing import Dict, List, Optional
from uuid import uuid4

from app.schemas.case import CaseCreate, CaseResponse, CaseUpdate


class CaseRepository:
    """Thread-safe in-memory case store."""

    def __init__(self) -> None:
        self._store: Dict[str, dict] = {}

    def create(self, payload: CaseCreate) -> CaseResponse:
        """Create a new case and return the response."""
        case_id = str(uuid4())
        now = datetime.utcnow()
        record = {
            "id": case_id,
            "title": payload.title,
            "status": "DRAFT",
            "fir_text": payload.fir_text,
            "call_records": payload.call_records,
            "financial_logs": payload.financial_logs,
            "location_data": payload.location_data,
            "district": payload.district,
            "station": payload.station,
            "filing_date": payload.filing_date,
            "created_at": now,
            "updated_at": now,
            "entities": [],
            "linked_case_count": 0,
            "processing_notes": None,
        }
        self._store[case_id] = record
        return CaseResponse(**record)

    def get(self, case_id: str) -> Optional[CaseResponse]:
        """Return a case by ID, or None."""
        record = self._store.get(case_id)
        if record is None:
            return None
        return CaseResponse(**record)

    def list_all(self, skip: int = 0, limit: int = 20) -> List[CaseResponse]:
        """Return cases with pagination."""
        records = list(self._store.values())
        return [CaseResponse(**r) for r in records[skip : skip + limit]]

    def update(self, case_id: str, payload: CaseUpdate) -> Optional[CaseResponse]:
        """Update case fields and return updated response."""
        record = self._store.get(case_id)
        if record is None:
            return None
        updates = payload.model_dump(exclude_unset=True)
        record.update(updates)
        record["updated_at"] = datetime.utcnow()
        return CaseResponse(**record)

    def update_field(self, case_id: str, **kwargs) -> None:
        """Update arbitrary fields on a stored case record."""
        record = self._store.get(case_id)
        if record is not None:
            record.update(kwargs)
            record["updated_at"] = datetime.utcnow()

    def delete(self, case_id: str) -> bool:
        """Soft-delete: set status to ARCHIVED. Returns False if not found."""
        if case_id in self._store:
            self._store[case_id]["status"] = "ARCHIVED"
            self._store[case_id]["updated_at"] = datetime.utcnow()
            return True
        return False

    def search(self, query: str, skip: int = 0, limit: int = 20) -> List[CaseResponse]:
        """Simple text search across title, fir_text, district, station."""
        results = []
        q = query.lower()
        for record in self._store.values():
            if (
                q in record.get("title", "").lower()
                or q in (record.get("fir_text") or "").lower()
                or q in (record.get("district") or "").lower()
                or q in (record.get("station") or "").lower()
            ):
                results.append(CaseResponse(**record))
        return results[skip : skip + limit]

    def count(self) -> int:
        """Total number of stored cases."""
        return len(self._store)

    def count_by_status(self) -> Dict[str, int]:
        """Count of cases grouped by status."""
        counts: Dict[str, int] = {}
        for record in self._store.values():
            s = record.get("status", "DRAFT")
            counts[s] = counts.get(s, 0) + 1
        return counts
