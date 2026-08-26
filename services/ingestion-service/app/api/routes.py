from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Ingestion"])

@router.post("/ingest/fir")
async def ingest_fir(payload: dict):
    return {"status": "ok", "message": "FIR ingestion placeholder"}

@router.post("/ingest/cdr")
async def ingest_cdr(payload: dict):
    return {"status": "ok", "message": "CDR ingestion placeholder"}

@router.post("/ingest/transactions")
async def ingest_transactions(payload: dict):
    return {"status": "ok", "message": "Transaction ingestion placeholder"}
