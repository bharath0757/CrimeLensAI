from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StructuredRecordsRequest(BaseModel):
    kind: Literal["cdr", "transactions"]
    records: list[dict] = Field(min_length=1, max_length=20_000)


class IngestionReceipt(BaseModel):
    id: str
    case_id: str
    document_id: str
    kind: Literal["cdr", "transactions"]
    source_sha256: str
    record_count: int
    inserted_records: int
    duplicate_records: int
    status: Literal["PENDING", "COMPLETED"]
    graph_cursor: int
    graph_total: int
    created_at: datetime
    completed_at: datetime | None
    last_error: str | None
