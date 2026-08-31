from fastapi import APIRouter
from app.services.pipeline import process_fir, FIRPayload

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])

@router.post("/ingest/fir")
async def ingest_fir(payload: FIRPayload):
    result = await process_fir(payload)
    return {"status": "ok", "message": "FIR ingested successfully", "result": result}

@router.post("/ingest/cdr")
async def ingest_cdr(payload: dict):
    return {"status": "ok", "message": "CDR ingestion placeholder"}

@router.post("/ingest/transactions")
async def ingest_transactions(payload: dict):
    return {"status": "ok", "message": "Transaction ingestion placeholder"}
