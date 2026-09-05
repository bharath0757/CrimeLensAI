"""PostgreSQL repository implementations used in deployed environments."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime
from functools import lru_cache
from typing import Any

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine

from app.core.audit_context import audit_actor, audit_request_id
from app.core.config import settings
from app.core.entity_identity import normalized_entity_value
from app.core.exceptions import CrimeLensException
from app.core.security import get_password_hash
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.repositories.user_repo import UserRepositoryInterface
from app.schemas.case import (
    CaseCreate,
    CasePriority,
    CaseResponse,
    CaseStatus,
    CaseUpdate,
)
from app.schemas.document import DocumentResponse, ProcessingStatus
from app.schemas.entity import EntityCreate, EntityResponse, EntityUpdate
from app.schemas.relationship import (
    RelationshipCreate,
    RelationshipResponse,
    RelationshipUpdate,
)
from app.schemas.user import UserCreate, UserResponse, UserUpdate


@lru_cache
def get_engine() -> Engine:
    engine = create_engine(
        settings.DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
    )
    @event.listens_for(engine, "begin")
    def attribute_transaction(connection):
        connection.execute(text(
            "SELECT set_config('crimelens.actor', :actor, true), "
            "set_config('crimelens.request_id', :request_id, true)"
        ), {"actor": audit_actor.get(), "request_id": audit_request_id.get()})
    return engine


async def _run(operation):
    return await asyncio.to_thread(operation)


def _json(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"))


def _enum(value: Any) -> Any:
    return value.value if hasattr(value, "value") else value


class PostgresUserRepository(UserRepositoryInterface):
    @staticmethod
    def _response(row) -> UserResponse | None:
        return UserResponse(**dict(row)) if row else None

    async def get_by_id(self, user_id: str) -> UserResponse | None:
        def operation():
            with get_engine().connect() as connection:
                row = connection.execute(
                    text("SELECT * FROM users WHERE id=:id"),
                    {"id": user_id},
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def get_by_email(self, email: str) -> UserResponse | None:
        def operation():
            with get_engine().connect() as connection:
                row = connection.execute(
                    text("SELECT * FROM users WHERE lower(email)=lower(:email)"),
                    {"email": email},
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def create(self, user_create: UserCreate) -> UserResponse:
        def operation():
            now = datetime.now(UTC)
            values = {
                "id": f"user-{uuid.uuid4().hex[:12]}",
                "email": user_create.email.lower(),
                "password_hash": get_password_hash(user_create.password),
                "full_name": user_create.full_name,
                "role": user_create.role.value,
                "badge_number": user_create.badge_number,
                "agency": user_create.agency,
                "created_at": now,
                "updated_at": now,
            }
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(
                        "INSERT INTO users "
                        "(id,email,password_hash,full_name,role,badge_number,agency,created_at,updated_at) "
                        "VALUES (:id,:email,:password_hash,:full_name,:role,:badge_number,:agency,:created_at,:updated_at) "
                        "RETURNING *"
                    ),
                    values,
                ).mappings().one()
                return self._response(row)
        return await _run(operation)

    async def get_password_hash(self, email: str) -> str | None:
        def operation():
            with get_engine().connect() as connection:
                return connection.execute(
                    text("SELECT password_hash FROM users WHERE lower(email)=lower(:email)"),
                    {"email": email},
                ).scalar_one_or_none()
        return await _run(operation)

    async def list_all(self, skip: int = 0, limit: int = 100) -> list[UserResponse]:
        def operation():
            with get_engine().connect() as connection:
                rows = connection.execute(
                    text("SELECT * FROM users ORDER BY created_at LIMIT :limit OFFSET :skip"),
                    {"limit": limit, "skip": skip},
                ).mappings()
                return [self._response(row) for row in rows]
        return await _run(operation)

    async def update(self, user_id: str, update_data: UserUpdate) -> UserResponse | None:
        values = update_data.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(user_id)
        values = {key: _enum(value) for key, value in values.items()}
        values.update(id=user_id, updated_at=datetime.now(UTC))
        assignments = ", ".join(f"{key}=:{key}" for key in values if key not in {"id", "updated_at"})
        def operation():
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(f"UPDATE users SET {assignments}, updated_at=:updated_at WHERE id=:id RETURNING *"),
                    values,
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def count(self) -> int:
        return await _run(lambda: _scalar("SELECT count(*) FROM users"))


class PostgresCaseRepository(CaseRepositoryInterface):
    @staticmethod
    def _response(row) -> CaseResponse | None:
        return CaseResponse(**dict(row)) if row else None

    async def get_by_id(self, case_id: str) -> CaseResponse | None:
        return await self._get("id", case_id)

    async def get_by_number(self, case_number: str) -> CaseResponse | None:
        return await self._get("case_number", case_number)

    async def _get(self, column: str, value: str) -> CaseResponse | None:
        def operation():
            with get_engine().connect() as connection:
                row = connection.execute(
                    text(f"SELECT * FROM cases WHERE {column}=:{column}"),
                    {column: value},
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def list_cases(
        self,
        skip: int = 0,
        limit: int = 50,
        status: CaseStatus | None = None,
        priority: CasePriority | None = None,
        owner_id: str | None = None,
        search_query: str | None = None,
    ) -> tuple[list[CaseResponse], int]:
        clauses = ["1=1"]
        params: dict[str, Any] = {"skip": skip, "limit": limit}
        if status:
            clauses.append("status=:status")
            params["status"] = status.value
        if priority:
            clauses.append("priority=:priority")
            params["priority"] = priority.value
        if owner_id:
            clauses.append("(owner_id=:owner_id OR assigned_investigator_ids @> CAST(:owner_json AS JSONB))")
            params.update(owner_id=owner_id, owner_json=_json([owner_id]))
        if search_query:
            clauses.append(
                "(case_number ILIKE :search OR title ILIKE :search OR description ILIKE :search OR complaint ILIKE :search)"
            )
            params["search"] = f"%{search_query}%"
        where = " AND ".join(clauses)
        def operation():
            with get_engine().connect() as connection:
                total = connection.execute(
                    text(f"SELECT count(*) FROM cases WHERE {where}"),
                    params,
                ).scalar_one()
                rows = connection.execute(
                    text(f"SELECT * FROM cases WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
                    params,
                ).mappings()
                return [self._response(row) for row in rows], total
        return await _run(operation)

    async def create(self, case_create: CaseCreate, owner_id: str) -> CaseResponse:
        def operation():
            now = datetime.now(UTC)
            case_id = f"case-{uuid.uuid4().hex[:12]}"
            values = {
                "id": case_id,
                "case_number": case_create.case_number or f"CASE-{now.year}-{uuid.uuid4().hex[:8].upper()}",
                "title": case_create.title,
                "description": case_create.description,
                "priority": case_create.priority.value,
                "owner_id": owner_id,
                "assigned": _json(sorted({owner_id, *case_create.assigned_investigator_ids})),
                "tags": _json(case_create.tags),
                "created_at": now,
                "updated_at": now,
            }
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(
                        "INSERT INTO cases "
                        "(id,case_number,title,description,priority,owner_id,assigned_investigator_ids,tags,created_at,updated_at) "
                        "VALUES (:id,:case_number,:title,:description,:priority,:owner_id,"
                        "CAST(:assigned AS JSONB),CAST(:tags AS JSONB),:created_at,:updated_at) RETURNING *"
                    ),
                    values,
                ).mappings().one()
                return self._response(row)
        return await _run(operation)

    async def update(self, case_id: str, case_update: CaseUpdate) -> CaseResponse | None:
        values = case_update.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(case_id)
        json_fields = {"assigned_investigator_ids", "tags"}
        assignments = []
        params: dict[str, Any] = {"id": case_id, "updated_at": datetime.now(UTC)}
        for key, value in values.items():
            if value is None:
                continue
            params[key] = _json(value) if key in json_fields else _enum(value)
            assignments.append(
                f"{key}=CAST(:{key} AS JSONB)" if key in json_fields else f"{key}=:{key}"
            )
        if not assignments:
            return await self.get_by_id(case_id)
        def operation():
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(f"UPDATE cases SET {', '.join(assignments)}, updated_at=:updated_at WHERE id=:id RETURNING *"),
                    params,
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def update_counts(
        self,
        case_id: str,
        doc_delta: int = 0,
        entity_delta: int = 0,
        rel_delta: int = 0,
    ) -> None:
        def operation():
            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        "UPDATE cases SET "
                        "document_count=greatest(0,document_count+:docs), "
                        "entity_count=greatest(0,entity_count+:entities), "
                        "relationship_count=greatest(0,relationship_count+:relationships), "
                        "updated_at=NOW() WHERE id=:id"
                    ),
                    {"id": case_id, "docs": doc_delta, "entities": entity_delta, "relationships": rel_delta},
                )
        await _run(operation)

    async def delete(self, case_id: str) -> bool:
        def operation():
            with get_engine().begin() as connection:
                result = connection.execute(text("DELETE FROM cases WHERE id=:id"), {"id": case_id})
                return result.rowcount > 0
        return await _run(operation)

    async def count(self, status: CaseStatus | None = None) -> int:
        if status is None:
            return await _run(lambda: _scalar("SELECT count(*) FROM cases"))
        return await _run(lambda: _scalar("SELECT count(*) FROM cases WHERE status=:status", {"status": status.value}))


class PostgresDocumentRepository(DocumentRepositoryInterface):
    @staticmethod
    def _response(row) -> DocumentResponse | None:
        return DocumentResponse(**dict(row)) if row else None

    async def get_by_id(self, doc_id: str) -> DocumentResponse | None:
        return await _run(lambda: self._get(doc_id))

    def _get(self, doc_id: str) -> DocumentResponse | None:
        with get_engine().connect() as connection:
            row = connection.execute(text("SELECT * FROM documents WHERE id=:id"), {"id": doc_id}).mappings().first()
            return self._response(row)

    async def list_by_case(self, case_id: str, skip: int = 0, limit: int = 50):
        def operation():
            with get_engine().connect() as connection:
                total = connection.execute(text("SELECT count(*) FROM documents WHERE case_id=:id"), {"id": case_id}).scalar_one()
                rows = connection.execute(
                    text("SELECT * FROM documents WHERE case_id=:id ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
                    {"id": case_id, "limit": limit, "skip": skip},
                ).mappings()
                return [self._response(row) for row in rows], total
        return await _run(operation)

    async def create(self, case_id, filename, original_filename, file_type, file_size_bytes, file_path, uploaded_by):
        def operation():
            now = datetime.now(UTC)
            params = {
                "id": f"doc-{uuid.uuid4().hex[:12]}",
                "case_id": case_id,
                "filename": filename,
                "original_filename": original_filename,
                "file_type": file_type,
                "file_size_bytes": file_size_bytes,
                "file_path": file_path,
                "uploaded_by": uploaded_by,
                "created_at": now,
                "updated_at": now,
            }
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(
                        "INSERT INTO documents "
                        "(id,case_id,filename,original_filename,file_type,file_size_bytes,file_path,uploaded_by,created_at,updated_at) "
                        "VALUES (:id,:case_id,:filename,:original_filename,:file_type,:file_size_bytes,:file_path,:uploaded_by,:created_at,:updated_at) "
                        "RETURNING *"
                    ),
                    params,
                ).mappings().one()
                return self._response(row)
        return await _run(operation)

    async def update_status(self, doc_id: str, status: ProcessingStatus, error_message: str | None = None):
        def operation():
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(
                        "UPDATE documents SET processing_status=:status,error_message=:error,updated_at=NOW() "
                        "WHERE id=:id RETURNING *"
                    ),
                    {"id": doc_id, "status": status.value, "error": error_message},
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def update_extraction_counts(self, doc_id: str, entity_count: int, relationship_count: int):
        def operation():
            with get_engine().begin() as connection:
                connection.execute(
                    text(
                        "UPDATE documents SET extracted_entity_count=extracted_entity_count+:entities,"
                        "extracted_relationship_count=extracted_relationship_count+:relationships,updated_at=NOW() WHERE id=:id"
                    ),
                    {"id": doc_id, "entities": entity_count, "relationships": relationship_count},
                )
        await _run(operation)

    async def delete(self, doc_id: str) -> str | None:
        def operation():
            with get_engine().begin() as connection:
                return connection.execute(
                    text("DELETE FROM documents WHERE id=:id RETURNING file_path"),
                    {"id": doc_id},
                ).scalar_one_or_none()
        return await _run(operation)

    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50):
        clauses = ["(original_filename ILIKE :query OR filename ILIKE :query OR file_type ILIKE :query)"]
        params = {"query": f"%{query}%", "skip": skip, "limit": limit}
        if case_id:
            clauses.append("case_id=:case_id")
            params["case_id"] = case_id
        where = " AND ".join(clauses)
        def operation():
            with get_engine().connect() as connection:
                total = connection.execute(text(f"SELECT count(*) FROM documents WHERE {where}"), params).scalar_one()
                rows = connection.execute(
                    text(f"SELECT * FROM documents WHERE {where} ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
                    params,
                ).mappings()
                return [self._response(row) for row in rows], total
        return await _run(operation)

    async def count(self, status: ProcessingStatus | None = None) -> int:
        if status is None:
            return await _run(lambda: _scalar("SELECT count(*) FROM documents"))
        return await _run(lambda: _scalar("SELECT count(*) FROM documents WHERE processing_status=:status", {"status": status.value}))


class PostgresEntityRepository(EntityRepositoryInterface):
    @staticmethod
    def _response(row) -> EntityResponse | None:
        return EntityResponse(**dict(row)) if row else None

    async def get_by_id(self, entity_id: str) -> EntityResponse | None:
        return await _run(lambda: self._get("id=:value", {"value": entity_id}))

    async def get_by_name_and_case(self, name: str, case_id: str) -> EntityResponse | None:
        return await _run(
            lambda: self._get(
                "case_id=:case_id AND lower(name)=lower(:name)",
                {"case_id": case_id, "name": name},
            )
        )

    def _get(self, where: str, params: dict[str, Any]) -> EntityResponse | None:
        with get_engine().connect() as connection:
            row = connection.execute(text(f"SELECT * FROM entities WHERE {where}"), params).mappings().first()
            return self._response(row)

    async def list_by_case(self, case_id, skip=0, limit=50, entity_type=None, search_query=None):
        clauses = ["case_id=:case_id"]
        params = {"case_id": case_id, "skip": skip, "limit": limit}
        if entity_type:
            clauses.append("entity_type=:entity_type")
            params["entity_type"] = entity_type.value
        if search_query:
            clauses.append("(name ILIKE :query OR description ILIKE :query)")
            params["query"] = f"%{search_query}%"
        return await _run(lambda: self._list(" AND ".join(clauses), params))

    def _list(self, where: str, params: dict[str, Any]):
        with get_engine().connect() as connection:
            total = connection.execute(text(f"SELECT count(*) FROM entities WHERE {where}"), params).scalar_one()
            rows = connection.execute(
                text(f"SELECT * FROM entities WHERE {where} ORDER BY created_at LIMIT :limit OFFSET :skip"),
                params,
            ).mappings()
            return [self._response(row) for row in rows], total

    async def create(self, case_id: str, entity_create: EntityCreate) -> EntityResponse:
        def operation():
            normalized = normalized_entity_value(entity_create.entity_type, entity_create.name)
            params = {
                "id": f"ent-{uuid.uuid4().hex[:12]}",
                "case_id": case_id,
                "name": entity_create.name,
                "normalized": normalized,
                "entity_type": entity_create.entity_type.value,
                "description": entity_create.description,
                "properties": _json(entity_create.properties),
                "confidence": entity_create.confidence_score,
                "source_document_id": entity_create.source_document_id,
            }
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(
                        "INSERT INTO entities "
                        "(id,case_id,name,normalized_value,entity_type,description,properties,confidence_score,source_document_id) "
                        "VALUES (:id,:case_id,:name,:normalized,:entity_type,:description,CAST(:properties AS JSONB),:confidence,:source_document_id) "
                        "ON CONFLICT (case_id,entity_type,normalized_value) DO UPDATE SET "
                        "confidence_score=greatest(entities.confidence_score,EXCLUDED.confidence_score), "
                        "properties=(entities.properties || EXCLUDED.properties) || jsonb_build_object('occurrences', "
                        "(SELECT COALESCE(jsonb_agg(DISTINCT mention),'[]'::jsonb) FROM jsonb_array_elements("
                        "COALESCE(entities.properties->'occurrences','[]'::jsonb) || "
                        "COALESCE(EXCLUDED.properties->'occurrences','[]'::jsonb)) AS mention)), "
                        "updated_at=NOW() RETURNING *"
                    ),
                    params,
                ).mappings().one()
                return self._response(row)
        return await _run(operation)

    async def update(self, entity_id: str, entity_update: EntityUpdate) -> EntityResponse | None:
        values = entity_update.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(entity_id)
        assignments = []
        params: dict[str, Any] = {"id": entity_id}
        for key, value in values.items():
            if value is None:
                continue
            column = "properties" if key == "properties" else key
            params[key] = _json(value) if key == "properties" else _enum(value)
            assignments.append(f"{column}=CAST(:{key} AS JSONB)" if key == "properties" else f"{column}=:{key}")
        def operation():
            with get_engine().begin() as connection:
                current = connection.execute(text("SELECT * FROM entities WHERE id=:id FOR UPDATE"), {"id": entity_id}).mappings().first()
                if not current:
                    return None
                if "name" in params or "entity_type" in params:
                    params["normalized_value"] = normalized_entity_value(
                        params.get("entity_type", current["entity_type"]), params.get("name", current["name"]),
                    )
                    assignments.append("normalized_value=:normalized_value")
                if not assignments:
                    return self._response(current)
                row = connection.execute(
                    text(f"UPDATE entities SET {', '.join(assignments)},updated_at=NOW() WHERE id=:id RETURNING *"),
                    params,
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def delete(self, entity_id: str) -> bool:
        return await _run(lambda: _delete("entities", entity_id))

    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50):
        clauses = ["(name ILIKE :query OR entity_type ILIKE :query OR description ILIKE :query)"]
        params = {"query": f"%{query}%", "skip": skip, "limit": limit}
        if case_id:
            clauses.append("case_id=:case_id")
            params["case_id"] = case_id
        return await _run(lambda: self._list(" AND ".join(clauses), params))

    async def count(self, case_id: str | None = None) -> int:
        if case_id:
            return await _run(lambda: _scalar("SELECT count(*) FROM entities WHERE case_id=:id", {"id": case_id}))
        return await _run(lambda: _scalar("SELECT count(*) FROM entities"))

    async def count_by_type(self) -> dict[str, int]:
        def operation():
            with get_engine().connect() as connection:
                rows = connection.execute(text("SELECT entity_type,count(*) AS count FROM entities GROUP BY entity_type")).mappings()
                return {row["entity_type"]: row["count"] for row in rows}
        return await _run(operation)

    async def set_review_status(self, entity_id: str, review_status: str) -> EntityResponse | None:
        if review_status not in {"PENDING", "CONFIRMED", "REJECTED"}:
            raise ValueError("Unsupported review status")
        def operation():
            with get_engine().begin() as connection:
                row = connection.execute(
                    text("UPDATE entities SET review_status=:status,updated_at=NOW() WHERE id=:id RETURNING *"),
                    {"id": entity_id, "status": review_status},
                ).mappings().first()
                return self._response(row)
        return await _run(operation)


class PostgresRelationshipRepository(RelationshipRepositoryInterface):
    @staticmethod
    def _response(row) -> RelationshipResponse | None:
        return RelationshipResponse(**dict(row)) if row else None

    async def get_by_id(self, rel_id: str) -> RelationshipResponse | None:
        def operation():
            with get_engine().connect() as connection:
                row = connection.execute(text("SELECT * FROM relationships WHERE id=:id"), {"id": rel_id}).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def list_by_case(self, case_id, skip=0, limit=50, relationship_type=None):
        clauses = ["case_id=:case_id"]
        params = {"case_id": case_id, "skip": skip, "limit": limit}
        if relationship_type:
            clauses.append("relationship_type=:relationship_type")
            params["relationship_type"] = relationship_type.value
        return await _run(lambda: self._list(" AND ".join(clauses), params))

    async def list_by_entity(self, entity_id: str) -> list[RelationshipResponse]:
        def operation():
            with get_engine().connect() as connection:
                rows = connection.execute(
                    text("SELECT * FROM relationships WHERE source_entity_id=:id OR target_entity_id=:id"),
                    {"id": entity_id},
                ).mappings()
                return [self._response(row) for row in rows]
        return await _run(operation)

    def _list(self, where: str, params: dict[str, Any]):
        with get_engine().connect() as connection:
            total = connection.execute(text(f"SELECT count(*) FROM relationships WHERE {where}"), params).scalar_one()
            rows = connection.execute(
                text(f"SELECT * FROM relationships WHERE {where} ORDER BY created_at LIMIT :limit OFFSET :skip"),
                params,
            ).mappings()
            return [self._response(row) for row in rows], total

    async def create(self, case_id: str, rel_create: RelationshipCreate) -> RelationshipResponse:
        evidence_key = str(rel_create.properties.get("transaction_id") or rel_create.properties.get("cdr_id")
                           or rel_create.properties.get("evidence_record_id") or f"document:{rel_create.source_document_id or 'manual'}")
        def operation():
            with get_engine().begin() as connection:
                existing = connection.execute(
                    text(
                        "SELECT * FROM relationships WHERE case_id=:case_id AND source_entity_id=:source "
                        "AND target_entity_id=:target AND relationship_type=:relationship_type "
                        "AND coalesce(properties->>'transaction_id',properties->>'cdr_id',properties->>'evidence_record_id',"
                        "'document:' || coalesce(source_document_id,'manual'))=:evidence_key LIMIT 1"
                    ),
                    {
                        "case_id": case_id,
                        "source": rel_create.source_entity_id,
                        "target": rel_create.target_entity_id,
                        "relationship_type": rel_create.relationship_type.value,
                        "evidence_key": evidence_key,
                    },
                ).mappings().first()
                if existing:
                    if existing["properties"] != rel_create.properties:
                        raise CrimeLensException(message="Evidence identifier already exists with different properties", status_code=409)
                    return self._response(existing)
                params = {
                    "id": "rel-" + uuid.uuid5(uuid.NAMESPACE_URL,
                        f"{case_id}:{rel_create.source_entity_id}:{rel_create.target_entity_id}:"
                        f"{rel_create.relationship_type.value}:{evidence_key}").hex,
                    "case_id": case_id,
                    "source": rel_create.source_entity_id,
                    "target": rel_create.target_entity_id,
                    "relationship_type": rel_create.relationship_type.value,
                    "description": rel_create.description,
                    "properties": _json(rel_create.properties),
                    "confidence": rel_create.confidence_score,
                    "source_document_id": rel_create.source_document_id,
                }
                row = connection.execute(
                    text(
                        "INSERT INTO relationships "
                        "(id,case_id,source_entity_id,target_entity_id,relationship_type,description,properties,confidence_score,source_document_id) "
                        "VALUES (:id,:case_id,:source,:target,:relationship_type,:description,CAST(:properties AS JSONB),:confidence,:source_document_id) "
                        "ON CONFLICT (id) DO UPDATE SET id=relationships.id RETURNING *"
                    ),
                    params,
                ).mappings().one()
                if row["properties"] != rel_create.properties:
                    raise CrimeLensException(message="Evidence identifier already exists with different properties", status_code=409)
                return self._response(row)
        return await _run(operation)

    async def update(self, rel_id: str, rel_update: RelationshipUpdate) -> RelationshipResponse | None:
        values = rel_update.model_dump(exclude_unset=True)
        if not values:
            return await self.get_by_id(rel_id)
        assignments = []
        params: dict[str, Any] = {"id": rel_id}
        for key, value in values.items():
            if value is None:
                continue
            params[key] = _json(value) if key == "properties" else _enum(value)
            assignments.append(f"{key}=CAST(:{key} AS JSONB)" if key == "properties" else f"{key}=:{key}")
        def operation():
            with get_engine().begin() as connection:
                row = connection.execute(
                    text(f"UPDATE relationships SET {', '.join(assignments)},updated_at=NOW() WHERE id=:id RETURNING *"),
                    params,
                ).mappings().first()
                return self._response(row)
        return await _run(operation)

    async def delete(self, rel_id: str) -> bool:
        return await _run(lambda: _delete("relationships", rel_id))

    async def search(self, query: str, case_id: str | None = None, skip: int = 0, limit: int = 50):
        clauses = ["(relationship_type ILIKE :query OR description ILIKE :query)"]
        params = {"query": f"%{query}%", "skip": skip, "limit": limit}
        if case_id:
            clauses.append("case_id=:case_id")
            params["case_id"] = case_id
        return await _run(lambda: self._list(" AND ".join(clauses), params))

    async def count(self, case_id: str | None = None) -> int:
        if case_id:
            return await _run(lambda: _scalar("SELECT count(*) FROM relationships WHERE case_id=:id", {"id": case_id}))
        return await _run(lambda: _scalar("SELECT count(*) FROM relationships"))

    async def count_by_type(self) -> dict[str, int]:
        def operation():
            with get_engine().connect() as connection:
                rows = connection.execute(text("SELECT relationship_type,count(*) AS count FROM relationships GROUP BY relationship_type")).mappings()
                return {row["relationship_type"]: row["count"] for row in rows}
        return await _run(operation)


def _scalar(query: str, params: dict[str, Any] | None = None) -> int:
    with get_engine().connect() as connection:
        return int(connection.execute(text(query), params or {}).scalar_one())


def _delete(table: str, record_id: str) -> bool:
    if table not in {"entities", "relationships"}:
        raise ValueError("Unsupported table")
    with get_engine().begin() as connection:
        result = connection.execute(text(f"DELETE FROM {table} WHERE id=:id"), {"id": record_id})
        return result.rowcount > 0
