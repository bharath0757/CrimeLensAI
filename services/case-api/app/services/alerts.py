"""Officer-scoped graph alerts and durably recorded review acknowledgements."""

import asyncio
import json
from urllib.parse import quote
from uuid import NAMESPACE_URL, uuid4, uuid5

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.integrations.ledger_integration import ledger_service
from app.repositories.postgres import get_engine
from app.repositories.registry import case_repository
from app.schemas.dashboard import ConnectionAlert, ConnectionAlertPage
from app.schemas.user import UserResponse, UserRole


async def audit_alert_action(alert: ConnectionAlert, user: UserResponse, action: str):
    # Requests are individually logged; completion is idempotent across retries.
    operation_id = str(uuid5(NAMESPACE_URL, f"crimelens:{action}:{alert.id}:{user.id}")) if action == "ALERT_ACKNOWLEDGED" else str(uuid4())
    events = [{
        "event_id": str(uuid5(NAMESPACE_URL, f"{operation_id}:{case_id}")),
        "record_id": alert.id, "case_id": case_id, "actor": user.id,
        "action": action, "resource_type": "ALERT", "payload": {"case_ids": sorted(alert.case_ids)},
    } for case_id in sorted(alert.case_ids)]
    if settings.DATA_BACKEND == "postgres":
        def enqueue():
            with get_engine().begin() as connection:
                for event in events:
                    connection.execute(text("INSERT INTO audit_outbox(event_id,event) VALUES (CAST(:id AS uuid),CAST(:event AS jsonb)) ON CONFLICT(event_id) DO NOTHING"), {"id": event["event_id"], "event": json.dumps(event)})
        await asyncio.to_thread(enqueue)
    else:
        for event in events:
            await ledger_service.append(event)


class AlertService:
    def __init__(self, cases=case_repository, transport=None, audit=audit_alert_action):
        self.cases, self.transport, self.audit = cases, transport, audit
        self._acknowledged_alerts: set[str] = set()

    async def _request(self, method, path):
        try:
            async with httpx.AsyncClient(timeout=10, transport=self.transport) as client:
                response = await client.request(method, f"{settings.GRAPH_SERVICE_URL.rstrip('/')}/api/v1{path}",
                                                headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN})
                if response.status_code == 404:
                    raise HTTPException(404, "Connection alert not found")
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(503, "Connection alerts unavailable; retry after checking graph service health.") from exc

    async def _visible(self, user: UserResponse) -> list[ConnectionAlert]:
        elevated = user.role == UserRole.ADMIN
        case_ids, skip = set(), 0
        while True:
            page, total = await self.cases.list_cases(skip=skip, limit=500, owner_id=None if elevated else user.id)
            case_ids.update(case.id for case in page)
            skip += len(page)
            if not page or skip >= total:
                break
        if not case_ids:
            return []
        try:
            body = await self._request("GET", "/alerts")
            alerts = [ConnectionAlert.model_validate(item) for item in body["alerts"]]
        except Exception:
            if settings.DATA_BACKEND != "memory" or self.transport is not None:
                raise
            alerts = await self._memory_alerts(case_ids)
        # Never leak another case's ID, identifier or narrative through an explanation.
        return sorted((alert for alert in alerts if set(alert.case_ids).issubset(case_ids)),
                      key=lambda alert: (alert.status != "NEW", -alert.created_at.timestamp(), alert.id))

    async def _memory_alerts(self, visible_case_ids: set[str]) -> list[ConnectionAlert]:
        from collections import defaultdict
        from datetime import UTC, datetime
        from app.repositories.registry import entity_repository
        from app.schemas.entity import EntityType
        if not hasattr(entity_repository, "_entities"):
            return []
        shared = defaultdict(set)
        for ent in entity_repository._entities.values():
            cid = ent.get("case_id")
            if cid in visible_case_ids and ent.get("entity_type") in (EntityType.PHONE_NUMBER, EntityType.VEHICLE, EntityType.UPI_ID):
                val = ent.get("name", "").strip().casefold()
                if val:
                    shared[(ent["entity_type"].value, val)].add(cid)
        results = []
        for (etype, val), cids in sorted(shared.items()):
            if len(cids) >= 2:
                cid_list = sorted(cids)
                aid = f"alert-{etype.lower()}-{val.replace(' ', '_').replace('+', '')[:20]}"
                status = "ACKNOWLEDGED" if aid in self._acknowledged_alerts else "NEW"
                results.append(ConnectionAlert(
                    id=aid,
                    case_ids=cid_list,
                    severity="HIGH" if etype in ("PHONE_NUMBER", "UPI_ID") else "MEDIUM",
                    status=status,
                    title=f"Cross-Case {etype.replace('_', ' ').title()} Overlap: {val}",
                    explanation=f"Shared {etype.replace('_', ' ').lower()} identified across cases {', '.join(cid_list[:3])}",
                    created_at=datetime.now(UTC),
                ))
        return results

    async def list(self, user: UserResponse, offset=0, limit=20):
        alerts = await self._visible(user)
        return ConnectionAlertPage(total=len(alerts), unread=sum(alert.status == "NEW" for alert in alerts), items=alerts[offset:offset + limit])

    async def acknowledge(self, alert_id: str, user: UserResponse):
        if user.role == UserRole.ANALYST:
            raise HTTPException(403, "Analysts have read-only alert access")
        alert = next((item for item in await self._visible(user) if item.id == alert_id), None)
        if not alert:
            raise HTTPException(404, "Connection alert not found")
        if settings.DATA_BACKEND == "memory" and self.transport is None:
            await self.audit(alert, user, "ALERT_ACK_REQUESTED")
            self._acknowledged_alerts.add(alert_id)
            ack = alert.model_copy(update={"status": "ACKNOWLEDGED"})
            await self.audit(ack, user, "ALERT_ACKNOWLEDGED")
            return ack
        await self.audit(alert, user, "ALERT_ACK_REQUESTED")
        result = await self._request("POST", f"/alerts/{quote(alert_id, safe='')}/acknowledge")
        try:
            acknowledged = ConnectionAlert.model_validate(result["alert"])
            if acknowledged.id != alert.id or set(acknowledged.case_ids) != set(alert.case_ids) or acknowledged.status != "ACKNOWLEDGED":
                raise ValueError("Unexpected acknowledgement")
        except (KeyError, TypeError, ValueError) as exc:
            raise HTTPException(502, "Invalid alert acknowledgement") from exc
        await self.audit(acknowledged, user, "ALERT_ACKNOWLEDGED")
        return acknowledged


alert_service = AlertService()


def get_alert_service() -> AlertService:
    return alert_service
