"""Authenticated audit service client and cryptographic in-memory hash ledger fallback."""

import hashlib
import hmac
import json
import logging
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ledger import (
    LedgerVerificationResponse,
    StoredLedgerChain,
    StoredLedgerRecord,
)

logger = logging.getLogger(__name__)

GENESIS = "0" * 64


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def record_hash(record: dict) -> str:
    body = {key: value for key, value in record.items() if key != "hash"}
    return hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


class InMemoryLedgerStore:
    """Tamper-evident in-memory SHA-256 hash-chain ledger for standalone / local execution."""

    def __init__(self):
        self._entries: list[dict] = []
        self._by_id: dict[str, dict] = {}
        self._by_record_id: dict[str, list[dict]] = {}
        self._head_sequence: int = 0
        self._head_hash: str = GENESIS

    def append(self, event: dict) -> dict:
        event_id = str(event.get("event_id") or event.get("id") or uuid.uuid4())
        record_id = str(event.get("record_id", event_id))
        case_id = event.get("case_id")
        actor = str(event.get("actor", "system"))
        action = str(event.get("action", "UNKNOWN"))
        resource_type = str(event.get("resource_type", "UNKNOWN"))
        payload = event.get("payload") or {}
        timestamp = event.get("timestamp") or datetime.now(UTC).isoformat(timespec="microseconds")

        if event_id in self._by_id:
            return self._by_id[event_id]

        self._head_sequence += 1
        previous_hash = self._head_hash

        record = {
            "version": 1,
            "sequence": self._head_sequence,
            "id": event_id,
            "record_id": record_id,
            "case_id": case_id,
            "actor": actor,
            "action": action,
            "resource_type": resource_type,
            "payload": payload,
            "timestamp": timestamp,
            "previous_hash": previous_hash,
        }
        record["hash"] = record_hash(record)
        self._head_hash = record["hash"]

        self._entries.append(record)
        self._by_id[event_id] = record
        self._by_record_id.setdefault(record_id, []).append(record)
        return record

    def append_many(self, events: list[dict]) -> list[dict]:
        return [self.append(ev) for ev in events]

    def chain(self, limit: int = 50, offset: int = 0, case_ids: list[str] | None = None) -> StoredLedgerChain:
        if case_ids is not None:
            filtered = [r for r in self._entries if r.get("case_id") in case_ids]
        else:
            filtered = list(self._entries)

        ordered = list(reversed(filtered))
        total = len(filtered)
        page = ordered[offset : offset + limit]

        return StoredLedgerChain(
            records=[StoredLedgerRecord(**r) for r in page],
            total=total,
            limit=limit,
            offset=offset,
        )

    def verify(self, record_id: str, case_ids: list[str] | None = None) -> LedgerVerificationResponse:
        target = self._by_id.get(record_id)
        if not target:
            candidates = self._by_record_id.get(record_id)
            if candidates:
                target = candidates[-1]
            else:
                for r in reversed(self._entries):
                    if r.get("id") == record_id or r.get("record_id") == record_id:
                        target = r
                        break

        if not target:
            raise HTTPException(status_code=404, detail="Audit record not found")

        if case_ids is not None and target.get("case_id") not in case_ids:
            raise HTTPException(status_code=404, detail="Audit record not found")

        expected_sequence = 1
        previous_hash = GENESIS
        error_sequence = None
        checked = 0

        for r in self._entries:
            checked += 1
            calculated_hash = record_hash(r)
            valid = (
                r["sequence"] == expected_sequence
                and r["previous_hash"] == previous_hash
                and hmac.compare_digest(calculated_hash, r["hash"])
            )
            if not valid:
                error_sequence = expected_sequence
                break
            previous_hash = r["hash"]
            expected_sequence += 1

        if error_sequence is None and (self._head_sequence != checked or self._head_hash != previous_hash):
            error_sequence = expected_sequence

        valid = error_sequence is None

        return LedgerVerificationResponse(
            record_id=record_id,
            event_id=target["id"],
            case_id=target.get("case_id"),
            verified=valid,
            status="VERIFIED" if valid else "TAMPERED",
            checked_records=checked,
            checked_through=self._head_sequence,
            checkpoint_hash=self._head_hash,
            error_sequence=error_sequence,
            message=(
                "Stored audit chain matches its checkpoint. Cryptographic SHA-256 hash-chain verified from genesis block."
                if valid
                else "Audit chain integrity check failed. Possible tamper detected."
            ),
        )


class LedgerService:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport
        self.local_store = InMemoryLedgerStore()

    def _should_use_remote(self) -> bool:
        if self.transport is not None:
            return True
        if settings.DATA_BACKEND == "postgres" and settings.SERVICE_AUTH_TOKEN and settings.LEDGER_SERVICE_URL:
            return True
        return False

    async def _request(self, method: str, path: str, *, params=None, json=None) -> dict:
        if not settings.SERVICE_AUTH_TOKEN:
            raise HTTPException(status_code=503, detail="Audit service credentials are not configured")
        try:
            async with httpx.AsyncClient(timeout=30, transport=self.transport) as client:
                response = await client.request(
                    method, f"{settings.LEDGER_SERVICE_URL.rstrip('/')}/api/v1/ledger{path}",
                    headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN}, params=params, json=json,
                )
                if response.status_code == 404:
                    raise HTTPException(status_code=404, detail="Audit record not found")
                if response.status_code == 409:
                    raise HTTPException(status_code=409, detail="Audit integrity or event ID conflict")
                response.raise_for_status()
                return response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise HTTPException(status_code=503, detail="Audit service unavailable; integrity is unverified") from exc

    @staticmethod
    def _filter_params(case_ids: list[str] | None):
        if case_ids == []:
            raise ValueError("An empty case filter must not become an unfiltered audit query")
        return [("case_id", case_id) for case_id in case_ids] if case_ids is not None else []

    async def chain(self, limit: int, offset: int, case_ids: list[str] | None) -> StoredLedgerChain:
        if not self._should_use_remote():
            return self.local_store.chain(limit, offset, case_ids)

        params = [("limit", str(limit)), ("offset", str(offset)), *self._filter_params(case_ids)]
        try:
            return StoredLedgerChain.model_validate(await self._request("GET", "/chain", params=params))
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Invalid audit service response") from exc

    async def verify(self, record_id: str, case_ids: list[str] | None) -> LedgerVerificationResponse:
        if not self._should_use_remote():
            return self.local_store.verify(record_id, case_ids)

        from urllib.parse import quote

        try:
            return LedgerVerificationResponse.model_validate(await self._request(
                "GET", f"/verify/{quote(record_id, safe='')}", params=self._filter_params(case_ids),
            ))
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Invalid audit verification response") from exc

    async def append(self, event: dict) -> dict:
        if not self._should_use_remote():
            return self.local_store.append(event)
        return await self._request("POST", "/record", json=event)

    async def append_many(self, events: list[dict]) -> dict:
        if not self._should_use_remote():
            records = self.local_store.append_many(events)
            return {"status": "RECORDED", "records": records}
        return await self._request("POST", "/batch", json={"events": events})


ledger_service = LedgerService()


def get_ledger_service() -> LedgerService:
    return ledger_service
