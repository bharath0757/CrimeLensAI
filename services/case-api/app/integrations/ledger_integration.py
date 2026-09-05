"""Authenticated audit service client. Network failure never becomes verification success."""

import httpx
from fastapi import HTTPException
from pydantic import ValidationError

from app.core.config import settings
from app.schemas.ledger import LedgerVerificationResponse, StoredLedgerChain


class LedgerService:
    def __init__(self, transport: httpx.AsyncBaseTransport | None = None):
        self.transport = transport

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
        params = [("limit", str(limit)), ("offset", str(offset)), *self._filter_params(case_ids)]
        try:
            return StoredLedgerChain.model_validate(await self._request("GET", "/chain", params=params))
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Invalid audit service response") from exc

    async def verify(self, record_id: str, case_ids: list[str] | None) -> LedgerVerificationResponse:
        from urllib.parse import quote

        try:
            return LedgerVerificationResponse.model_validate(await self._request(
                "GET", f"/verify/{quote(record_id, safe='')}", params=self._filter_params(case_ids),
            ))
        except ValidationError as exc:
            raise HTTPException(status_code=502, detail="Invalid audit verification response") from exc

    async def append(self, event: dict) -> dict:
        return await self._request("POST", "/record", json=event)

    async def append_many(self, events: list[dict]) -> dict:
        return await self._request("POST", "/batch", json={"events": events})


ledger_service = LedgerService()


def get_ledger_service() -> LedgerService:
    return ledger_service
