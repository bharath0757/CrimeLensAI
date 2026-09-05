"""Portable evidence metadata; financial values remain exact across graph storage."""

from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvidenceSource(BaseModel):
    model_config = ConfigDict(extra="forbid")
    document_id: str = Field(min_length=1, max_length=200)
    row_number: int = Field(ge=1)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class RelationshipEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    timestamp: datetime
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    currency: Literal["INR"] | None = None
    duration: int | None = Field(default=None, ge=0, le=86_400)
    tower: str | None = Field(default=None, max_length=200)
    imei: str | None = Field(default=None, pattern=r"^[0-9]{15}$")
    upi: str | None = Field(default=None, max_length=200)
    sources: list[EvidenceSource] = Field(min_length=1, max_length=20_000)

    @field_validator("amount")
    @classmethod
    def exact_rupees(cls, value):
        return value.quantize(Decimal("0.01")) if value is not None else None

    @model_validator(mode="after")
    def currency_matches_money(self):
        if (self.amount is None) != (self.currency is None):
            raise ValueError("Amount and currency must be supplied together")
        return self

    @field_validator("timestamp")
    @classmethod
    def timestamp_has_timezone(cls, value):
        if value.tzinfo is None:
            raise ValueError("Evidence timestamp requires a timezone")
        return value.astimezone(UTC)
