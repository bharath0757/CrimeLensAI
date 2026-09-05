"""Leased, resumable delivery of committed structured evidence into Neo4j."""

import asyncio
import logging
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.audit_context import audit_actor
from app.core.config import settings
from app.repositories.postgres import get_engine

logger = logging.getLogger(__name__)


class IngestionDelivery:
    def __init__(self, engine_factory=get_engine, transport=None):
        self.engine_factory, self.transport = engine_factory, transport
        self.stop = asyncio.Event()

    def ensure_ready(self):
        with self.engine_factory().connect() as connection:
            versions = connection.execute(text(
                "SELECT version FROM schema_migrations WHERE version IN ('002_structured_ingestion','003_runtime_roles')"
            )).scalars().all()
            protected = connection.execute(text(
                "SELECT 1 FROM pg_trigger WHERE tgname='protect_ingestion_evidence' "
                "AND tgrelid=to_regclass('ingestion_batches') AND tgenabled='O'"
            )).scalar_one_or_none()
            if set(versions) != {"002_structured_ingestion", "003_runtime_roles"} or protected is None:
                raise RuntimeError("Structured ingestion database migration is missing")

    def _claim(self):
        with self.engine_factory().begin() as connection:
            row = connection.execute(text("""WITH candidate AS (
                SELECT id FROM ingestion_batches WHERE status='PENDING' AND next_attempt_at <= NOW()
                AND (claimed_until IS NULL OR claimed_until<NOW()) ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED)
                UPDATE ingestion_batches b SET claim_token=CAST(:token AS uuid),claimed_until=NOW()+INTERVAL '90 seconds',attempts=attempts+1
                FROM candidate c WHERE b.id=c.id RETURNING b.*"""), {"token": str(uuid4())}).mappings().first()
            return dict(row) if row else None

    def _advance(self, batch, cursor, error=None):
        completed = cursor == len(batch["graph_operations"]) and error is None
        actor_token = audit_actor.set(batch["actor"])
        try:
            with self.engine_factory().begin() as connection:
                row = connection.execute(text("""UPDATE ingestion_batches SET graph_cursor=:cursor,
                    status=:status,completed_at=CASE WHEN :complete THEN NOW() ELSE NULL END,
                    claim_token=NULL,claimed_until=NULL,last_error=:error,
                    next_attempt_at=NOW()+(:delay * INTERVAL '1 second')
                    WHERE id=:id AND claim_token=:token RETURNING document_id"""), {
                        "id": batch["id"], "token": batch["claim_token"], "cursor": cursor,
                        "status": "COMPLETED" if completed else "PENDING", "complete": completed,
                        "error": error, "delay": min(300, 2 ** min(batch["attempts"], 8)) if error else 0,
                    }).scalar_one_or_none()
                if row and completed:
                    connection.execute(text("UPDATE documents SET processing_status='COMPLETED',updated_at=NOW() WHERE id=:id"), {"id": row})
        finally:
            audit_actor.reset(actor_token)

    async def deliver_one(self):
        batch = await asyncio.to_thread(self._claim)
        if batch is None:
            return False
        cursor = batch["graph_cursor"]
        chunk = batch["graph_operations"][cursor:cursor + 100]
        try:
            async with httpx.AsyncClient(timeout=60, transport=self.transport) as client:
                response = await client.post(f"{settings.GRAPH_SERVICE_URL.rstrip('/')}/api/v1/batches", json={"operations": chunk}, headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN})
                response.raise_for_status()
                if response.json().get("processed") != len(chunk):
                    raise ValueError("Graph receipt did not acknowledge the complete chunk")
            await asyncio.to_thread(self._advance, batch, cursor + len(chunk))
        except (httpx.HTTPError, ValueError, SQLAlchemyError) as exc:
            logger.warning("Structured graph delivery deferred: batch=%s reason=%s", batch["id"], type(exc).__name__)
            await asyncio.to_thread(self._advance, batch, cursor, type(exc).__name__)
        return True

    async def run(self):
        while not self.stop.is_set():
            try:
                worked = await self.deliver_one()
            except SQLAlchemyError as exc:
                logger.error("Ingestion queue database failure: %s", type(exc).__name__)
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=1)
                except TimeoutError:
                    continue
