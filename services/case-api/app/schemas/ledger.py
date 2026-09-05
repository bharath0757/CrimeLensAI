"""Audit gateway models; an unverified record is never labelled verified."""

from typing import Any

from pydantic import BaseModel


class StoredLedgerRecord(BaseModel):
    id: str
    sequence: int
    timestamp: str
    record_id: str
    case_id: str | None
    actor: str
    action: str
    resource_type: str
    payload: dict[str, Any]
    hash: str
    previous_hash: str


class StoredLedgerChain(BaseModel):
    records: list[StoredLedgerRecord]
    total: int
    limit: int
    offset: int


class LedgerRecordResponse(BaseModel):
    id: str
    sequence: int
    timestamp: str
    action: str
    actor: str
    resource: str
    dataHash: str
    previous_hash: str
    status: str = "UNVERIFIED"
    verified: bool | None = None


class LedgerChainResponse(BaseModel):
    total: int
    offset: int
    limit: int
    items: list[LedgerRecordResponse]


class LedgerVerificationResponse(BaseModel):
    record_id: str
    event_id: str
    case_id: str | None
    verified: bool
    status: str
    checked_records: int
    checked_through: int
    checkpoint_hash: str
    error_sequence: int | None = None
    message: str
