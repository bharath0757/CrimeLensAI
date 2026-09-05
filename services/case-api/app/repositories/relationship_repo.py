import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipResponse,
    RelationshipType,
    RelationshipUpdate,
)


class RelationshipRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, rel_id: str) -> RelationshipResponse | None:
        pass

    @abstractmethod
    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        relationship_type: RelationshipType | None = None,
    ) -> tuple[list[RelationshipResponse], int]:
        pass

    @abstractmethod
    async def list_by_entity(self, entity_id: str) -> list[RelationshipResponse]:
        pass

    @abstractmethod
    async def create(self, case_id: str, rel_create: RelationshipCreate) -> RelationshipResponse:
        pass

    @abstractmethod
    async def update(self, rel_id: str, rel_update: RelationshipUpdate) -> RelationshipResponse | None:
        pass

    @abstractmethod
    async def delete(self, rel_id: str) -> bool:
        pass

    @abstractmethod
    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50) -> tuple[list[RelationshipResponse], int]:
        pass

    @abstractmethod
    async def count(self, case_id: str | None = None) -> int:
        pass

    @abstractmethod
    async def count_by_type(self) -> dict[str, int]:
        pass


class InMemoryRelationshipRepository(RelationshipRepositoryInterface):
    """In-memory Relationship Repository implementation."""

    def __init__(self):
        self._relationships: dict[str, dict[str, Any]] = {}

    async def get_by_id(self, rel_id: str) -> RelationshipResponse | None:
        r = self._relationships.get(rel_id)
        if not r:
            return None
        return RelationshipResponse(**r)

    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        relationship_type: RelationshipType | None = None,
    ) -> tuple[list[RelationshipResponse], int]:
        filtered = [r for r in self._relationships.values() if r["case_id"] == case_id]
        if relationship_type:
            filtered = [r for r in filtered if r["relationship_type"] == relationship_type]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [RelationshipResponse(**r) for r in paginated], total

    async def list_by_entity(self, entity_id: str) -> list[RelationshipResponse]:
        filtered = [
            r for r in self._relationships.values()
            if r["source_entity_id"] == entity_id or r["target_entity_id"] == entity_id
        ]
        return [RelationshipResponse(**r) for r in filtered]

    async def create(self, case_id: str, rel_create: RelationshipCreate) -> RelationshipResponse:
        # Check duplicate
        for r in self._relationships.values():
            if (
                r["case_id"] == case_id
                and r["source_entity_id"] == rel_create.source_entity_id
                and r["target_entity_id"] == rel_create.target_entity_id
                and r["relationship_type"] == rel_create.relationship_type
            ):
                return RelationshipResponse(**r)

        rel_id = f"rel-{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC)
        rel_dict = {
            "id": rel_id,
            "case_id": case_id,
            "source_entity_id": rel_create.source_entity_id,
            "target_entity_id": rel_create.target_entity_id,
            "relationship_type": rel_create.relationship_type,
            "description": rel_create.description,
            "properties": rel_create.properties,
            "confidence_score": rel_create.confidence_score,
            "source_document_id": rel_create.source_document_id,
            "created_at": now,
            "updated_at": now,
        }
        self._relationships[rel_id] = rel_dict
        return RelationshipResponse(**rel_dict)

    async def update(self, rel_id: str, rel_update: RelationshipUpdate) -> RelationshipResponse | None:
        r = self._relationships.get(rel_id)
        if not r:
            return None
        update_dict = rel_update.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                r[k] = v
        r["updated_at"] = datetime.now(UTC)
        return RelationshipResponse(**r)

    async def delete(self, rel_id: str) -> bool:
        if rel_id in self._relationships:
            del self._relationships[rel_id]
            return True
        return False

    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50) -> tuple[list[RelationshipResponse], int]:
        q = query.lower()
        filtered = list(self._relationships.values())
        if case_id:
            filtered = [r for r in filtered if r["case_id"] == case_id]
        filtered = [
            r for r in filtered
            if q in r["relationship_type"].lower() or (r.get("description") and q in r["description"].lower())
        ]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [RelationshipResponse(**r) for r in paginated], total

    async def count(self, case_id: str | None = None) -> int:
        if not case_id:
            return len(self._relationships)
        return sum(1 for r in self._relationships.values() if r["case_id"] == case_id)

    async def count_by_type(self) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for r in self._relationships.values():
            t = r["relationship_type"]
            breakdown[t] = breakdown.get(t, 0) + 1
        return breakdown


relationship_repository = InMemoryRelationshipRepository()
