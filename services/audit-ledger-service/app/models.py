"""Versioned ledger wire models; hashes cover all immutable event fields."""

import json
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


class AppendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    record_id: str = Field(min_length=1, max_length=200)
    case_id: str | None = Field(default=None, min_length=1, max_length=200)
    actor: str = Field(min_length=1, max_length=200)
    action: str = Field(min_length=1, max_length=100)
    resource_type: str = Field(min_length=1, max_length=100)
    payload: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def bounded_payload(self):
        try:
            serialized = canonical_json(self.payload)
        except (TypeError, ValueError, RecursionError) as exc:
            raise ValueError("Payload must be finite JSON data") from exc
        if len(serialized.encode("utf-8")) > 65_536:
            raise ValueError("Audit payload exceeds 64 KiB")
        return self


class LedgerRecord(BaseModel):
    version: int = 1
    sequence: int
    id: str
    record_id: str
    case_id: str | None
    actor: str
    action: str
    resource_type: str
    payload: dict[str, Any]
    timestamp: str
    previous_hash: str
    hash: str


class AppendResponse(BaseModel):
    status: str = "RECORDED"
    record: LedgerRecord


class BatchAppendRequest(BaseModel):
    events: list[AppendRequest] = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def unique_event_ids(self):
        identifiers = [event.event_id for event in self.events]
        if len(identifiers) != len(set(identifiers)):
            raise ValueError("A ledger batch cannot contain duplicate event IDs")
        return self


class BatchAppendResponse(BaseModel):
    status: str = "RECORDED"
    records: list[LedgerRecord]


class ChainResponse(BaseModel):
    records: list[LedgerRecord]
    total: int
    limit: int
    offset: int


class VerificationResponse(BaseModel):
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


SENSITIVE_FIELDS = {
    "victim_name", "victim_address", "victim_phone", "victim_email",
    "aadhaar", "pan", "passport", "bank_account",
}


class MaskRequest(BaseModel):
    data: dict[str, Any]
    sensitive_fields: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def bounded_data(self):
        if len(canonical_json(self.data).encode("utf-8")) > 65_536:
            raise ValueError("Masking input exceeds 64 KiB")
        return self


class MaskResponse(BaseModel):
    masked_data: dict[str, Any]


class HealthResponse(BaseModel):
    status: str
    service: str = "ledger"
