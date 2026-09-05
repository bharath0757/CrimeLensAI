from typing import Annotated

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from app.models import ValidationRequest, ValidationResult
from app.parsers.structured import validate
from app.security import require_service_token
from app.services.pipeline import (
    CDRPayload,
    FIRPayload,
    TransactionPayload,
    process_cdr,
    process_fir,
    process_transaction,
)

router = APIRouter(prefix="/api/v1", tags=["Ingestion"], dependencies=[Depends(require_service_token)])
BearerHeader = Annotated[str | None, Header(alias="Authorization")]


class AdapterResponse(BaseModel):
    result: dict


@router.post("/validate", response_model=ValidationResult)
def validate_evidence(payload: ValidationRequest) -> ValidationResult:
    return validate(payload)


@router.post("/ingest/fir", response_model=AdapterResponse)
async def ingest_fir(payload: FIRPayload, authorization: BearerHeader = None):
    return AdapterResponse(result=await process_fir(payload, authorization))


@router.post("/ingest/cdr", response_model=AdapterResponse, status_code=202)
async def ingest_cdr(payload: CDRPayload, authorization: BearerHeader = None):
    return AdapterResponse(result=await process_cdr(payload, authorization))


@router.post("/ingest/transactions", response_model=AdapterResponse, status_code=202)
async def ingest_transactions(payload: TransactionPayload, authorization: BearerHeader = None):
    return AdapterResponse(result=await process_transaction(payload, authorization))
