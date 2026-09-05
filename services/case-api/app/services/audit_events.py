"""Queue non-CRUD security events for durable delivery to the hash ledger."""

from __future__ import annotations

import asyncio
import json
import uuid
from datetime import UTC, datetime

from sqlalchemy import text

from app.core.config import settings
from app.integrations.ledger_integration import ledger_service


async def record_security_event(
    *, actor: str, action: str, resource_type: str, record_id: str,
    case_id: str | None, payload: dict,
) -> str:
    event_id = str(uuid.uuid4())
    event = {
        "event_id": event_id,
        "record_id": record_id,
        "case_id": case_id,
        "actor": actor,
        "action": action,
        "resource_type": resource_type,
        "payload": {**payload, "requested_at": datetime.now(UTC).isoformat()},
    }
    if settings.DATA_BACKEND == "postgres":
        from app.repositories.postgres import get_engine

        def enqueue() -> None:
            with get_engine().begin() as connection:
                connection.execute(
                    text("INSERT INTO audit_outbox(event_id,event) VALUES (CAST(:id AS UUID),CAST(:event AS JSONB))"),
                    {"id": event_id, "event": json.dumps(event, separators=(",", ":"))},
                )

        await asyncio.to_thread(enqueue)
    else:
        await ledger_service.append(event)
    return event_id
