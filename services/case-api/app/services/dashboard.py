"""Case-scoped dashboard aggregates. No fabricated metrics or activity events."""

import asyncio
import json
from collections import Counter, defaultdict
from collections.abc import Iterable
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import settings
from app.core.entity_identity import normalized_entity_value
from app.repositories.postgres import get_engine
from app.repositories.registry import (
    case_repository,
    document_repository,
    entity_repository,
    relationship_repository,
)
from app.schemas.dashboard import (
    DashboardMetrics,
    DashboardOverview,
    DashboardStatisticsResponse,
    DashboardSummaryResponse,
)
from app.schemas.user import UserResponse, UserRole

STRONG_IDENTIFIERS = {"PHONE_NUMBER", "PHONE", "UPI_ID", "BANK_ACCOUNT", "VEHICLE", "EMAIL", "AADHAAR", "PAN", "PASSPORT"}
SCOPE = """WITH visible_cases AS (
    SELECT c.* FROM cases c WHERE :elevated OR c.owner_id=:user_id
    OR c.assigned_investigator_ids @> CAST(:assignment AS jsonb)
) """


def scope_parameters(user: UserResponse) -> dict:
    return {"elevated": user.role == UserRole.ADMIN,
            "user_id": user.id, "assignment": json.dumps([user.id]), "strong": sorted(STRONG_IDENTIFIERS)}


def count_linked_networks(groups: Iterable[Iterable[str]]) -> int:
    """Union shared-identifier case groups without constructing all pairwise edges."""
    parents: dict[str, str] = {}

    def root(item):
        parents.setdefault(item, item)
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    for group in groups:
        members = list(set(group))
        if len(members) < 2:
            continue
        first = root(members[0])
        for member in members[1:]:
            parents[root(member)] = first
    return len({root(item) for item in parents})


def _assemble(backend, cases, entities, relationships, documents, groups, money, timeline, activities, investigators):
    status_counts = Counter(case["status"] for case in cases)
    priority_counts = Counter(case["priority"] for case in cases)
    entity_counts = dict(entities["types"])
    relationship_counts = dict(relationships)
    active = status_counts["OPEN"] + status_counts["IN_PROGRESS"]
    metrics = DashboardMetrics(
        total_cases=len(cases), high_risk_cases=priority_counts["HIGH"] + priority_counts["CRITICAL"],
        linked_networks=count_linked_networks(groups), money_flow=money, active_investigations=active,
        total_entities=sum(entity_counts.values()), total_relationships=sum(relationship_counts.values()),
        pending_reviews=entities["pending"],
    )
    return DashboardOverview(
        generated_at=datetime.now(UTC), data_backend=backend, metrics=metrics,
        summary=DashboardSummaryResponse(
            total_cases=len(cases), active_cases=active, closed_cases=status_counts["CLOSED"],
            total_documents=sum(documents.values()), total_entities=metrics.total_entities,
            total_relationships=metrics.total_relationships, total_investigators=len(investigators),
        ),
        statistics=DashboardStatisticsResponse(
            cases_by_status=dict(status_counts), cases_by_priority=dict(priority_counts),
            entities_by_type=entity_counts, relationships_by_type=relationship_counts,
            documents_by_status=dict(documents), recent_activities=activities, transaction_timeline=timeline,
        ),
    )


class DashboardService:
    def __init__(self, cases=case_repository, entities=entity_repository, documents=document_repository,
                 relationships=relationship_repository, engine_factory=get_engine):
        self.cases, self.entities, self.documents, self.relationships = cases, entities, documents, relationships
        self.engine_factory = engine_factory

    async def overview(self, user: UserResponse) -> DashboardOverview:
        if settings.DATA_BACKEND == "postgres":
            return await asyncio.to_thread(self._postgres, user)
        return await self._memory(user)

    def _postgres(self, user):
        parameters = scope_parameters(user)
        # One snapshot prevents charts/totals observing different concurrent writes.
        with self.engine_factory().connect().execution_options(isolation_level="REPEATABLE READ") as connection:
            def rows(query):
                return connection.execute(text(SCOPE + query), parameters).mappings().all()

            cases = rows("SELECT id,status,priority,owner_id,assigned_investigator_ids FROM visible_cases")
            entity_rows = rows("SELECT e.entity_type AS label,count(*) AS total,count(*) FILTER (WHERE e.review_status='PENDING') AS pending FROM entities e JOIN visible_cases c ON c.id=e.case_id GROUP BY e.entity_type")
            entities = {"types": {row["label"]: row["total"] for row in entity_rows}, "pending": sum(row["pending"] for row in entity_rows)}
            relationships = {row["label"]: row["total"] for row in rows("SELECT r.relationship_type AS label,count(*) AS total FROM relationships r JOIN visible_cases c ON c.id=r.case_id GROUP BY r.relationship_type")}
            documents = {row["label"]: row["total"] for row in rows("SELECT d.processing_status AS label,count(*) AS total FROM documents d JOIN visible_cases c ON c.id=d.case_id GROUP BY d.processing_status")}
            groups = [row["case_ids"] for row in rows("SELECT array_agg(DISTINCT e.case_id) AS case_ids FROM entities e JOIN visible_cases c ON c.id=e.case_id WHERE e.entity_type=ANY(:strong) AND e.review_status<>'REJECTED' AND e.normalized_value<>'' GROUP BY e.entity_type,e.normalized_value HAVING count(DISTINCT e.case_id)>1")]
            money = rows("SELECT coalesce(sum(t.amount),0) AS total FROM transactions t JOIN visible_cases c ON c.id=t.case_id")[0]["total"]
            timeline = list(reversed(rows("SELECT (t.occurred_at AT TIME ZONE 'UTC')::date::text AS date,sum(t.amount) AS amount,count(*) AS count FROM transactions t JOIN visible_cases c ON c.id=t.case_id GROUP BY 1 ORDER BY 1 DESC LIMIT 30")))
            activity_rows = rows("SELECT o.event_id::text AS id,o.event->>'action' AS type,o.created_at AS timestamp,o.event->>'actor' AS actor,c.id AS case_id FROM audit_outbox o JOIN visible_cases c ON c.id=o.event->>'case_id' ORDER BY o.sequence DESC LIMIT 10")
            activities = [{**row, "description": row["type"].replace("_", " ")} for row in activity_rows]
        investigators = {case["owner_id"] for case in cases}
        investigators.update(item for case in cases for item in case["assigned_investigator_ids"])
        return _assemble("postgres", cases, entities, relationships, documents, groups, money, timeline, activities, investigators)

    @staticmethod
    async def _pages(fetch, **kwargs):
        result, skip = [], 0
        while True:
            page, total = await fetch(skip=skip, limit=500, **kwargs)
            result.extend(page)
            skip += len(page)
            if not page or skip >= total:
                return result

    async def _memory(self, user):
        owner = None if scope_parameters(user)["elevated"] else user.id
        cases = await self._pages(self.cases.list_cases, owner_id=owner)
        entities, relationships, documents = [], [], []
        for case in cases:
            entities.extend(await self._pages(self.entities.list_by_case, case_id=case.id))
            relationships.extend(await self._pages(self.relationships.list_by_case, case_id=case.id))
            documents.extend(await self._pages(self.documents.list_by_case, case_id=case.id))
        groups = defaultdict(set)
        for entity in entities:
            if entity.entity_type.value in STRONG_IDENTIFIERS and entity.review_status != "REJECTED":
                groups[(entity.entity_type.value, normalized_entity_value(entity.entity_type, entity.name))].add(entity.case_id)
        investigators = {case.owner_id for case in cases}
        investigators.update(item for case in cases for item in case.assigned_investigator_ids)
        # In-memory development mode has no transaction repository; do not invent money totals.
        activities = [{"id": case.id, "type": "CASE_CREATED", "description": "CASE CREATED", "timestamp": case.created_at,
                       "case_id": case.id, "actor": case.owner_id} for case in sorted(cases, key=lambda case: case.created_at, reverse=True)[:10]]
        return _assemble("memory", [case.model_dump(mode="json") for case in cases],
                         {"types": Counter(entity.entity_type.value for entity in entities), "pending": sum(entity.review_status == "PENDING" for entity in entities)},
                         Counter(relation.relationship_type.value for relation in relationships),
                         Counter(document.processing_status.value for document in documents), groups.values(), None, [], activities, investigators)


dashboard_service = DashboardService()


def get_dashboard_service() -> DashboardService:
    return dashboard_service
