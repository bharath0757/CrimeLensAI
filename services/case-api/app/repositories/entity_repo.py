import uuid
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timezone

from app.schemas.entity import EntityResponse, EntityCreate, EntityUpdate, EntityType


class EntityRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> Optional[EntityResponse]:
        pass

    @abstractmethod
    async def get_by_name_and_case(self, name: str, case_id: str) -> Optional[EntityResponse]:
        pass

    @abstractmethod
    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        entity_type: Optional[EntityType] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[EntityResponse], int]:
        pass

    @abstractmethod
    async def create(self, case_id: str, entity_create: EntityCreate) -> EntityResponse:
        pass

    @abstractmethod
    async def update(self, entity_id: str, entity_update: EntityUpdate) -> Optional[EntityResponse]:
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    async def search(self, query: str, case_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> Tuple[List[EntityResponse], int]:
        pass

    @abstractmethod
    async def count(self, case_id: Optional[str] = None) -> int:
        pass

    @abstractmethod
    async def count_by_type(self) -> Dict[str, int]:
        pass


class InMemoryEntityRepository(EntityRepositoryInterface):
    """In-memory Entity Repository implementation."""

    def __init__(self):
        self._entities: Dict[str, Dict[str, Any]] = {}

    async def get_by_id(self, entity_id: str) -> Optional[EntityResponse]:
        e = self._entities.get(entity_id)
        if not e:
            return None
        return EntityResponse(**e)

    async def get_by_name_and_case(self, name: str, case_id: str) -> Optional[EntityResponse]:
        for e in self._entities.values():
            if e["case_id"] == case_id and e["name"].lower() == name.lower():
                return EntityResponse(**e)
        return None

    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        entity_type: Optional[EntityType] = None,
        search_query: Optional[str] = None,
    ) -> Tuple[List[EntityResponse], int]:
        filtered = [e for e in self._entities.values() if e["case_id"] == case_id]
        if entity_type:
            filtered = [e for e in filtered if e["entity_type"] == entity_type]
        if search_query:
            q = search_query.lower()
            filtered = [
                e for e in filtered
                if q in e["name"].lower() or (e.get("description") and q in e["description"].lower())
            ]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [EntityResponse(**e) for e in paginated], total

    async def create(self, case_id: str, entity_create: EntityCreate) -> EntityResponse:
        existing = await self.get_by_name_and_case(entity_create.name, case_id)
        if existing:
            return existing

        entity_id = f"ent-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        entity_dict = {
            "id": entity_id,
            "case_id": case_id,
            "name": entity_create.name,
            "entity_type": entity_create.entity_type,
            "description": entity_create.description,
            "properties": entity_create.properties,
            "confidence_score": entity_create.confidence_score,
            "source_document_id": entity_create.source_document_id,
            "created_at": now,
            "updated_at": now,
        }
        self._entities[entity_id] = entity_dict
        return EntityResponse(**entity_dict)

    async def update(self, entity_id: str, entity_update: EntityUpdate) -> Optional[EntityResponse]:
        e = self._entities.get(entity_id)
        if not e:
            return None
        update_dict = entity_update.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                e[k] = v
        e["updated_at"] = datetime.now(timezone.utc)
        return EntityResponse(**e)

    async def delete(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    async def search(self, query: str, case_id: Optional[str] = None, skip: int = 0, limit: int = 50) -> Tuple[List[EntityResponse], int]:
        q = query.lower()
        filtered = list(self._entities.values())
        if case_id:
            filtered = [e for e in filtered if e["case_id"] == case_id]
        filtered = [
            e for e in filtered
            if q in e["name"].lower() or (e.get("description") and q in e["description"].lower()) or q in e["entity_type"].lower()
        ]
        total = len(filtered)
        paginated = filtered[skip : skip + limit]
        return [EntityResponse(**e) for e in paginated], total

    async def count(self, case_id: Optional[str] = None) -> int:
        if not case_id:
            return len(self._entities)
        return sum(1 for e in self._entities.values() if e["case_id"] == case_id)

    async def count_by_type(self) -> Dict[str, int]:
        breakdown: Dict[str, int] = {}
        for e in self._entities.values():
            t = e["entity_type"]
            breakdown[t] = breakdown.get(t, 0) + 1
        return breakdown


entity_repository = InMemoryEntityRepository()
