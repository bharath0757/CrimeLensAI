"""Lease-based delivery of transactionally captured audit events."""

import asyncio
import logging
from uuid import uuid4

import httpx
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.integrations.ledger_integration import LedgerService, ledger_service
from app.repositories.postgres import get_engine

logger = logging.getLogger(__name__)


class AuditDelivery:
    def __init__(self, ledger: LedgerService = ledger_service, engine_factory=get_engine):
        self.ledger = ledger
        self.engine_factory = engine_factory
        self.stop = asyncio.Event()

    def ensure_ready(self) -> None:
        with self.engine_factory().connect() as connection:
            version = connection.execute(text(
                "SELECT version FROM schema_migrations WHERE version='001_audit_outbox'"
            )).scalar_one_or_none()
            protections = connection.execute(text(
                "SELECT version FROM schema_migrations WHERE version='003_runtime_roles'"
            )).scalar_one_or_none()
            triggers = connection.execute(text(
                "SELECT count(*) FROM pg_trigger WHERE tgname='capture_domain_audit' AND tgenabled='O' "
                "AND tgrelid IN (to_regclass('users'),to_regclass('cases'),to_regclass('documents'),"
                "to_regclass('entities'),to_regclass('relationships'),to_regclass('cdr_records'),to_regclass('transactions'))"
            )).scalar_one()
            if version is None or protections is None or triggers != 7:
                raise RuntimeError("Database audit migration is missing or audit capture is disabled")

    def _claim_batch(self, limit: int = 500):
        token = str(uuid4())
        with self.engine_factory().begin() as connection:
            rows = connection.execute(text("""
                WITH candidate AS (
                    SELECT sequence FROM audit_outbox
                    WHERE delivered_at IS NULL AND next_attempt_at <= NOW()
                    AND (claimed_until IS NULL OR claimed_until < NOW())
                    ORDER BY sequence LIMIT :limit FOR UPDATE SKIP LOCKED
                ), claimed AS (
                    UPDATE audit_outbox AS item SET claim_token=CAST(:token AS UUID),
                        claimed_until=NOW()+INTERVAL '90 seconds', attempts=attempts+1
                    FROM candidate WHERE item.sequence=candidate.sequence
                    RETURNING item.sequence,item.event_id,item.event,item.attempts,item.claim_token
                )
                SELECT * FROM claimed ORDER BY sequence
            """), {"token": token, "limit": limit}).mappings().all()
            return [dict(row) for row in rows]

    def _claim(self):
        rows = self._claim_batch(1)
        return rows[0] if rows else None

    def _finish_batch(self, items, hashes: dict[str, str]):
        with self.engine_factory().begin() as connection:
            connection.execute(text("""
                UPDATE audit_outbox SET delivered_at=NOW(), ledger_hash=:hash,
                    claim_token=NULL, claimed_until=NULL, last_error=NULL
                WHERE sequence=:sequence AND claim_token=:token
            """), [
                {
                    "hash": hashes[str(item["event_id"])],
                    "sequence": item["sequence"],
                    "token": item["claim_token"],
                }
                for item in items
            ])

    def _retry_batch(self, items, error: str):
        with self.engine_factory().begin() as connection:
            connection.execute(text("""
                UPDATE audit_outbox SET claim_token=NULL, claimed_until=NULL,
                    next_attempt_at=NOW()+(:delay * INTERVAL '1 second'), last_error=:error
                WHERE sequence=:sequence AND claim_token=:token
            """), [
                {
                    "sequence": item["sequence"], "token": item["claim_token"],
                    "delay": min(300, 2 ** min(item["attempts"], 9)), "error": error,
                }
                for item in items
            ])

    @staticmethod
    def _delivery_event(item):
        event = item["event"]
        if event.get("resource_type") is None and event.get("action") is None:
            event = {
                **event,
                "resource_type": "UNCLASSIFIED",
                "action": "MALFORMED_CAPTURE_PRESERVED",
                "payload": {
                    "original_event": item["event"],
                    "warning": (
                        "Original database capture omitted resource/action; review the original "
                        "snapshot and migration history."
                    ),
                },
            }
            logger.warning("Preserving malformed legacy audit capture: event=%s", item["event_id"])
        return event

    async def deliver_one(self) -> bool:
        return await self.deliver_batch(1)

    async def deliver_batch(self, limit: int = 500) -> bool:
        items = await asyncio.to_thread(self._claim_batch, limit)
        if not items:
            return False
        try:
            events = [self._delivery_event(item) for item in items]
            if hasattr(self.ledger, "append_many"):
                records = (await self.ledger.append_many(events))["records"]
            else:
                records = [(await self.ledger.append(event))["record"] for event in events]
            if len(records) != len(items):
                raise ValueError("Ledger batch receipt count does not match the queue")
            hashes = {}
            for item, record in zip(items, records, strict=True):
                if record["id"] != str(item["event_id"]) or len(record["hash"]) != 64:
                    raise ValueError("Ledger receipt does not match the queued event")
                hashes[record["id"]] = record["hash"]
            await asyncio.to_thread(self._finish_batch, items, hashes)
        except (HTTPException, httpx.HTTPError, SQLAlchemyError, KeyError, ValueError, TypeError, TimeoutError) as exc:
            # Keep the original event and UUID. If the ledger committed before a
            # timeout, its idempotency check makes the retry safe.
            error = f"{type(exc).__name__}:{getattr(exc, 'status_code', 'delivery')}"
            logger.warning("Audit batch delivery deferred: first_event=%s size=%d reason=%s", items[0]["event_id"], len(items), error)
            await asyncio.to_thread(self._retry_batch, items, error)
        return True

    async def run(self):
        while not self.stop.is_set():
            try:
                worked = await self.deliver_batch()
            except SQLAlchemyError as exc:
                logger.error("Audit delivery database failure: %s", type(exc).__name__)
                worked = False
            if not worked:
                try:
                    await asyncio.wait_for(self.stop.wait(), timeout=1.0)
                except TimeoutError:
                    continue
