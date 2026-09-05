import asyncio
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import text

from app.api.deps import get_case_repository, get_current_user
from app.core.access import require_case_access
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.postgres import get_engine
from app.schemas.ingestion import IngestionReceipt, StructuredRecordsRequest
from app.schemas.user import UserResponse
from app.services.structured_ingestion import structured_ingestion, validate_evidence

router = APIRouter()
User = Annotated[UserResponse, Depends(get_current_user)]
Cases = Annotated[CaseRepositoryInterface, Depends(get_case_repository)]


@router.post("/cases/{case_id}/ingestion/csv", response_model=IngestionReceipt, status_code=202)
async def upload_structured_csv(case_id: str, kind: Literal["cdr", "transactions"], user: User, cases: Cases,
                                file: Annotated[UploadFile, File()]):
    case = await require_case_access(case_id, user, cases, write=True)
    contents = await file.read(10_485_761)
    await file.close()
    if len(contents) > 10_485_760:
        raise HTTPException(413, "Structured uploads must not exceed 10 MiB")
    try:
        source = contents.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(422, "Upload a UTF-8 CSV file") from exc
    result = await validate_evidence(kind, case, source_text=source)
    filename = (file.filename or "evidence.csv").replace("\\", "/").split("/")[-1][:200]
    return await structured_ingestion.ingest(case.id, user.id, kind, result, source, filename)


@router.post("/cases/{case_id}/ingestion/records", response_model=IngestionReceipt, status_code=202)
async def upload_structured_records(case_id: str, payload: StructuredRecordsRequest, user: User, cases: Cases):
    case = await require_case_access(case_id, user, cases, write=True)
    try:
        source = json.dumps(payload.records, sort_keys=True, ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise HTTPException(422, "Evidence must contain finite JSON values") from exc
    if len(source.encode()) > 10_485_760:
        raise HTTPException(413, "Structured uploads must not exceed 10 MiB")
    result = await validate_evidence(payload.kind, case, records=payload.records)
    return await structured_ingestion.ingest(case.id, user.id, payload.kind, result, source, "evidence.json")


@router.get("/cases/{case_id}/ingestion/{batch_id}", response_model=IngestionReceipt)
async def ingestion_status(case_id: str, batch_id: str, user: User, cases: Cases):
    await require_case_access(case_id, user, cases)
    return await structured_ingestion.get(case_id, batch_id)


@router.get("/cases/{case_id}/ingestion/{batch_id}/source", response_class=Response)
async def ingestion_source(case_id: str, batch_id: str, user: User, cases: Cases):
    await require_case_access(case_id, user, cases)
    def load():
        with get_engine().connect() as connection:
            row = connection.execute(text("SELECT source_text,source_sha256 FROM ingestion_batches WHERE id=:id AND case_id=:case"), {"id": batch_id, "case": case_id}).mappings().first()
            if row is None:
                raise HTTPException(404, "Ingestion source not found")
            return dict(row)
    row = await asyncio.to_thread(load)
    return Response(row["source_text"], media_type="text/plain", headers={"Content-Disposition": 'attachment; filename="structured-evidence.txt"', "X-Content-SHA256": row["source_sha256"], "Cache-Control": "no-store"})
