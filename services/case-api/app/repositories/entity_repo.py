import uuid
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from typing import Any

from app.core.entity_identity import normalized_entity_value
from app.schemas.entity import EntityCreate, EntityResponse, EntityType, EntityUpdate


class EntityRepositoryInterface(ABC):
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> EntityResponse | None:
        pass

    @abstractmethod
    async def get_by_name_and_case(self, name: str, case_id: str) -> EntityResponse | None:
        pass

    @abstractmethod
    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        entity_type: EntityType | None = None,
        search_query: str | None = None,
    ) -> tuple[list[EntityResponse], int]:
        pass

    @abstractmethod
    async def create(self, case_id: str, entity_create: EntityCreate) -> EntityResponse:
        pass

    @abstractmethod
    async def update(self, entity_id: str, entity_update: EntityUpdate) -> EntityResponse | None:
        pass

    @abstractmethod
    async def delete(self, entity_id: str) -> bool:
        pass

    @abstractmethod
    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50) -> tuple[list[EntityResponse], int]:
        pass

    @abstractmethod
    async def count(self, case_id: str | None = None) -> int:
        pass

    @abstractmethod
    async def count_by_type(self) -> dict[str, int]:
        pass

    @abstractmethod
    async def set_review_status(self, entity_id: str, review_status: str) -> EntityResponse | None:
        pass


class InMemoryEntityRepository(EntityRepositoryInterface):
    """In-memory Entity Repository implementation."""

    def __init__(self):
        self._entities: dict[str, dict[str, Any]] = {}
        self._seed_sample_entities()

    def _seed_sample_entities(self):
        now = datetime.now(UTC)
        seeds = [
            {
                "id": "ent-sample-001",
                "case_id": "case-sample-001",
                "name": "Vikram Sharma",
                "entity_type": EntityType.PERSON,
                "description": "Primary suspect in cyber fraud syndicate",
                "properties": {},
                "confidence_score": 0.95,
                "review_status": "PENDING",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "ent-sample-002",
                "case_id": "case-sample-001",
                "name": "9876543210",
                "entity_type": EntityType.PHONE_NUMBER,
                "description": "Suspect communication phone number",
                "properties": {},
                "confidence_score": 0.98,
                "review_status": "CONFIRMED",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "ent-sample-003",
                "case_id": "case-sample-001",
                "name": "UP32-AB-1234",
                "entity_type": EntityType.VEHICLE,
                "description": "Vehicle identified near crime scene",
                "properties": {},
                "confidence_score": 0.88,
                "review_status": "PENDING",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "ent-sample-004",
                "case_id": "case-sample-002",
                "name": "9876543210",
                "entity_type": EntityType.PHONE_NUMBER,
                "description": "Shared contact phone number across Hawala network",
                "properties": {},
                "confidence_score": 0.98,
                "review_status": "CONFIRMED",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "ent-sample-005",
                "case_id": "case-sample-002",
                "name": "Lucknow Main Branch",
                "entity_type": EntityType.LOCATION,
                "description": "Hawala money drop location",
                "properties": {},
                "confidence_score": 0.90,
                "review_status": "PENDING",
                "created_at": now,
                "updated_at": now,
            },
        ]
        for s in seeds:
            self._entities[s["id"]] = s

    async def get_by_id(self, entity_id: str) -> EntityResponse | None:
        e = self._entities.get(entity_id)
        if not e:
            return None
        return EntityResponse(**e)

    async def get_by_name_and_case(self, name: str, case_id: str) -> EntityResponse | None:
        for e in self._entities.values():
            if e["case_id"] == case_id and e["name"].lower() == name.lower():
                return EntityResponse(**e)
        return None

    async def list_by_case(
        self,
        case_id: str,
        skip: int = 0,
        limit: int = 50,
        entity_type: EntityType | None = None,
        search_query: str | None = None,
    ) -> tuple[list[EntityResponse], int]:
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
        normalized = normalized_entity_value(entity_create.entity_type, entity_create.name)
        for existing in self._entities.values():
            if (existing["case_id"] == case_id and existing["entity_type"] == entity_create.entity_type
                    and normalized_entity_value(existing["entity_type"], existing["name"]) == normalized):
                return EntityResponse(**existing)

        entity_id = f"ent-{uuid.uuid4().hex[:8]}"
        now = datetime.now(UTC)
        entity_dict = {
            "id": entity_id,
            "case_id": case_id,
            "name": entity_create.name,
            "entity_type": entity_create.entity_type,
            "description": entity_create.description,
            "properties": entity_create.properties,
            "confidence_score": entity_create.confidence_score,
            "source_document_id": entity_create.source_document_id,
            "review_status": "PENDING",
            "created_at": now,
            "updated_at": now,
        }
        self._entities[entity_id] = entity_dict
        return EntityResponse(**entity_dict)

    async def update(self, entity_id: str, entity_update: EntityUpdate) -> EntityResponse | None:
        e = self._entities.get(entity_id)
        if not e:
            return None
        update_dict = entity_update.model_dump(exclude_unset=True)
        for k, v in update_dict.items():
            if v is not None:
                e[k] = v
        e["updated_at"] = datetime.now(UTC)
        return EntityResponse(**e)

    async def delete(self, entity_id: str) -> bool:
        if entity_id in self._entities:
            del self._entities[entity_id]
            return True
        return False

    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50) -> tuple[list[EntityResponse], int]:
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

    async def count(self, case_id: str | None = None) -> int:
        if not case_id:
            return len(self._entities)
        return sum(1 for e in self._entities.values() if e["case_id"] == case_id)

    async def count_by_type(self) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for e in self._entities.values():
            t = e["entity_type"]
            breakdown[t] = breakdown.get(t, 0) + 1
        return breakdown

    async def set_review_status(self, entity_id: str, review_status: str) -> EntityResponse | None:
        if review_status not in {"PENDING", "CONFIRMED", "REJECTED"}:
            raise ValueError("Unsupported review status")
        entity = self._entities.get(entity_id)
        if not entity:
            return None
        entity["review_status"] = review_status
        entity["updated_at"] = datetime.now(UTC)
        return EntityResponse(**entity)


entity_repository = InMemoryEntityRepository()
