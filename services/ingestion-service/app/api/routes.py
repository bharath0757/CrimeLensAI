
from fastapi import APIRouter
from app.services.pipeline import (
    process_fir, FIRPayload,
    process_cdr, CDRPayload,
    process_transaction, TransactionPayload
)

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])

@router.post("/ingest/fir")
async def ingest_fir(payload: FIRPayload):
    result = await process_fir(payload)
    return {"status": "ok", "message": "FIR ingested successfully", "result": result}

@router.post("/ingest/cdr")
async def ingest_cdr(payload: CDRPayload):
    result = await process_cdr(payload)
    return {"status": "ok", "message": "CDR processed", "result": result}

@router.post("/ingest/transactions")
async def ingest_transactions(payload: TransactionPayload):
    result = await process_transaction(payload)
    return {"status": "ok", "message": "Transaction processed", "result": result}
