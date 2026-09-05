import asyncio
import os
import uuid
from contextlib import suppress
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from app.api.deps import (
    get_ai_service,
    get_case_repository,
    get_current_user,
    get_document_repository,
)
from app.core.access import require_case_access
from app.core.config import settings
from app.integrations.ai_integration import AIServiceInterface
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.schemas.document import (
    DocumentListResponse,
    DocumentProcessingStatusResponse,
    DocumentResponse,
)
from app.schemas.user import UserResponse
from app.services.document_text import DocumentTextError

router = APIRouter()
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]
CaseRepository = Annotated[CaseRepositoryInterface, Depends(get_case_repository)]
DocumentRepository = Annotated[DocumentRepositoryInterface, Depends(get_document_repository)]
AIService = Annotated[AIServiceInterface, Depends(get_ai_service)]


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal security vulnerabilities."""
    base_name = os.path.basename(filename)
    return base_name.replace("..", "").replace("/", "").replace("\\", "")


@router.post("/cases/{case_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload Evidence Document")
async def upload_document(
    case_id: str,
    file: Annotated[UploadFile, File()],
    current_user: CurrentUser,
    case_repo: CaseRepository,
    doc_repo: DocumentRepository,
) -> Any:
    """Upload evidence document for a case with strict file type and size validation."""
    await require_case_access(case_id, current_user, case_repo, write=True)

    clean_filename = sanitize_filename(file.filename or "file.bin")
    file_ext = clean_filename.split(".")[-1].lower() if "." in clean_filename else ""

    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{file_ext}'. Allowed extensions: {settings.ALLOWED_EXTENSIONS}",
        )

    # Read and check size
    file_content = await file.read(settings.MAX_FILE_SIZE_BYTES + 1)
    if len(file_content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f}MB.",
        )

    # Ensure uploads directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_filename = f"{uuid.uuid4().hex}_{clean_filename}"
    saved_filepath = os.path.join(settings.UPLOAD_DIR, saved_filename)

    await asyncio.to_thread(Path(saved_filepath).write_bytes, file_content)

    document = await doc_repo.create(
        case_id=case_id,
        filename=saved_filename,
        original_filename=clean_filename,
        file_type=file_ext,
        file_size_bytes=len(file_content),
        file_path=saved_filepath,
        uploaded_by=current_user.email,
    )

    await case_repo.update_counts(case_id, doc_delta=1)
    return document


@router.get("/cases/{case_id}/documents", response_model=DocumentListResponse, summary="List Case Documents")
async def list_case_documents(
    case_id: str,
    current_user: CurrentUser,
    case_repo: CaseRepository,
    doc_repo: DocumentRepository,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
) -> Any:
    """Retrieve all evidence documents uploaded for a specific case."""
    await require_case_access(case_id, current_user, case_repo)

    items, total = await doc_repo.list_by_case(case_id, skip=skip, limit=limit)
    return DocumentListResponse(total=total, items=items)


@router.get("/documents/{document_id}", response_model=DocumentResponse, summary="Get Document Details")
async def get_document(
    document_id: str,
    current_user: CurrentUser,
    doc_repo: DocumentRepository,
    case_repo: CaseRepository,
) -> Any:
    """Retrieve document metadata and extraction status."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    await require_case_access(document.case_id, current_user, case_repo)
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Document")
async def delete_document(
    document_id: str,
    current_user: CurrentUser,
    case_repo: CaseRepository,
    doc_repo: DocumentRepository,
) -> None:
    """Delete document metadata and local file."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    await require_case_access(document.case_id, current_user, case_repo, write=True)
    file_path = await doc_repo.delete(document_id)
    if file_path and os.path.exists(file_path):
        with suppress(OSError):
            os.remove(file_path)

    await case_repo.update_counts(document.case_id, doc_delta=-1)


@router.post("/documents/{document_id}/process", summary="Trigger AI/NLP Document Processing")
async def process_document_ai(
    document_id: str,
    current_user: CurrentUser,
    doc_repo: DocumentRepository,
    ai_service: AIService,
    case_repo: CaseRepository,
) -> Any:
    """Trigger AI/NLP entity & relationship extraction pipeline via integration interface."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    await require_case_access(document.case_id, current_user, case_repo, write=True)
    try:
        success = await ai_service.process_document(
            document_id=document.id,
            case_id=document.case_id,
            file_path=document.file_path,
        )
    except DocumentTextError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not success:
        raise HTTPException(status_code=503, detail="Document processing did not complete. Check processing status and service health.")

    return {
        "success": True,
        "document_id": document.id,
        "case_id": document.case_id,
        "message": "Document extraction and graph synchronization completed.",
    }


@router.get("/documents/{document_id}/processing-status", response_model=DocumentProcessingStatusResponse, summary="Get AI Processing Status")
async def get_processing_status(
    document_id: str,
    current_user: CurrentUser,
    ai_service: AIService,
    doc_repo: DocumentRepository,
    case_repo: CaseRepository,
) -> Any:
    """Check status of AI/NLP processing pipeline for a document."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found.")
    await require_case_access(document.case_id, current_user, case_repo)
    return await ai_service.get_processing_status(document_id)
