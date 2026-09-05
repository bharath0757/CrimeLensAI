"""Bounded structured evidence contracts shared by the ingestion endpoints."""

import re
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Kind = Literal["cdr", "transactions"]


class ValidationRequest(BaseModel):
    kind: Kind
    case_id: str = Field(min_length=1, max_length=200)
    case_number: str | None = None
    csv_text: str | None = Field(default=None, max_length=10_485_760)
    records: list[dict] | None = Field(default=None, max_length=20_000)


class EvidenceRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    record_id: str = Field(min_length=1, max_length=200)
    row_number: int = Field(ge=1)
    source: str = Field(min_length=1, max_length=200)
    target: str = Field(min_length=1, max_length=200)
    source_type: Literal["PHONE_NUMBER", "BANK_ACCOUNT", "UPI_ID"]
    target_type: Literal["PHONE_NUMBER", "BANK_ACCOUNT", "UPI_ID"]
    timestamp: datetime
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    duration: int | None = Field(default=None, ge=0, le=86_400)
    tower: str | None = Field(default=None, min_length=1, max_length=200)
    imei: str | None = None
    upi: str | None = None
    transaction_type: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("timestamp")
    @classmethod
    def timezone_required(cls, value: datetime):
        if value.tzinfo is None:
            raise ValueError("timestamp must include timezone, for example +05:30 or Z")
        return value.astimezone(UTC)

    @field_validator("record_id", "tower")
    @classmethod
    def no_controls(cls, value):
        if value and re.search(r"[\x00-\x1f\x7f]", value):
            raise ValueError("Control characters are not allowed")
        return value


class ValidationResult(BaseModel):
    kind: Kind
    records: list[EvidenceRow]
    input_rows: int
    duplicate_rows: int
    warnings: list[str] = Field(default_factory=list)
