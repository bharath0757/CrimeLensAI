"""Internal service API. Officer identity and case access are enforced by case-api."""

import hmac
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.security import APIKeyHeader

from app.models import (
    SENSITIVE_FIELDS,
    AppendRequest,
    AppendResponse,
    BatchAppendRequest,
    BatchAppendResponse,
    ChainResponse,
    MaskRequest,
    MaskResponse,
    VerificationResponse,
)
from app.store import LedgerStore

service_key = APIKeyHeader(name="X-Service-Token", auto_error=False)


def require_service(request: Request, x_service_token: Annotated[str | None, Depends(service_key)]) -> None:
    expected = request.app.state.settings.SERVICE_AUTH_TOKEN
    if not expected or not x_service_token or not hmac.compare_digest(expected.encode(), x_service_token.encode()):
        raise HTTPException(status_code=401, detail="Invalid service credentials")


def get_store(request: Request) -> LedgerStore:
    return request.app.state.store


Store = Annotated[LedgerStore, Depends(get_store)]
CaseFilter = Annotated[list[str] | None, Query(max_length=1000)]
router = APIRouter(prefix="/api/v1", tags=["Ledger"], dependencies=[Depends(require_service)])


@router.post("/ledger/record", response_model=AppendResponse, status_code=201)
def append_record(payload: AppendRequest, store: Store) -> AppendResponse:
    return AppendResponse(record=store.append(payload))


@router.post("/ledger/batch", response_model=BatchAppendResponse, status_code=201)
def append_batch(payload: BatchAppendRequest, store: Store) -> BatchAppendResponse:
    return BatchAppendResponse(records=store.append_many(payload.events))


@router.get("/ledger/verify/{record_id}", response_model=VerificationResponse)
def verify_record(record_id: str, store: Store, case_id: CaseFilter = None) -> VerificationResponse:
    return store.verify(record_id, case_id)


@router.get("/ledger/chain", response_model=ChainResponse)
def get_chain(
    store: Store, limit: int = Query(50, ge=1, le=200), offset: int = Query(0, ge=0),
    case_id: CaseFilter = None,
) -> ChainResponse:
    return store.list_records(limit, offset, case_id)


@router.post("/privacy/mask", response_model=MaskResponse)
def mask_fields(payload: MaskRequest) -> MaskResponse:
    sensitive = SENSITIVE_FIELDS | {field.casefold() for field in payload.sensitive_fields}

    def masked(value):
        if isinstance(value, dict):
            return {key: "[REDACTED]" if key.casefold() in sensitive else masked(item) for key, item in value.items()}
        if isinstance(value, list):
            return [masked(item) for item in value]
        return value

    return MaskResponse(masked_data=masked(payload.data))
