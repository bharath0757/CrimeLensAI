import os
import uuid
import shutil
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, status

from app.core.config import settings
from app.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentProcessingStatusResponse,
)
from app.schemas.user import UserResponse
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.case_repo import CaseRepositoryInterface
from app.integrations.ai_integration import AIServiceInterface
from app.api.deps import (
    get_document_repository,
    get_case_repository,
    get_ai_service,
    get_current_user,
)

router = APIRouter()


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal security vulnerabilities."""
    base_name = os.path.basename(filename)
    return base_name.replace("..", "").replace("/", "").replace("\\", "")


@router.post("/cases/{case_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED, summary="Upload Evidence Document")
async def upload_document(
    case_id: str,
    file: UploadFile = File(...),
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
) -> Any:
    """Upload evidence document for a case with strict file type and size validation."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    clean_filename = sanitize_filename(file.filename or "file.bin")
    file_ext = clean_filename.split(".")[-1].lower() if "." in clean_filename else ""

    if file_ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '.{file_ext}'. Allowed extensions: {settings.ALLOWED_EXTENSIONS}",
        )

    # Read and check size
    file_content = await file.read()
    if len(file_content) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum limit of {settings.MAX_FILE_SIZE_BYTES / (1024 * 1024):.0f}MB.",
        )

    # Ensure uploads directory exists
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    saved_filename = f"{uuid.uuid4().hex}_{clean_filename}"
    saved_filepath = os.path.join(settings.UPLOAD_DIR, saved_filename)

    with open(saved_filepath, "wb") as f:
        f.write(file_content)

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
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
) -> Any:
    """Retrieve all evidence documents uploaded for a specific case."""
    case = await case_repo.get_by_id(case_id)
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case not found.")

    items, total = await doc_repo.list_by_case(case_id, skip=skip, limit=limit)
    return DocumentListResponse(total=total, items=items)


@router.get("/documents/{document_id}", response_model=DocumentResponse, summary="Get Document Details")
async def get_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
) -> Any:
    """Retrieve document metadata and extraction status."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")
    return document


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete Document")
async def delete_document(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user),
    case_repo: CaseRepositoryInterface = Depends(get_case_repository),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
) -> None:
    """Delete document metadata and local file."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    file_path = await doc_repo.delete(document_id)
    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except OSError:
            pass

    await case_repo.update_counts(document.case_id, doc_delta=-1)
    return None


@router.post("/documents/{document_id}/process", summary="Trigger AI/NLP Document Processing")
async def process_document_ai(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user),
    doc_repo: DocumentRepositoryInterface = Depends(get_document_repository),
    ai_service: AIServiceInterface = Depends(get_ai_service),
) -> Any:
    """Trigger AI/NLP entity & relationship extraction pipeline via integration interface."""
    document = await doc_repo.get_by_id(document_id)
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    success = await ai_service.process_document(
        document_id=document.id,
        case_id=document.case_id,
        file_path=document.file_path,
    )
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to dispatch document to AI service.")

    return {
        "success": True,
        "document_id": document.id,
        "case_id": document.case_id,
        "message": "AI/NLP entity extraction triggered successfully.",
    }


@router.get("/documents/{document_id}/processing-status", response_model=DocumentProcessingStatusResponse, summary="Get AI Processing Status")
async def get_processing_status(
    document_id: str,
    current_user: UserResponse = Depends(get_current_user),
    ai_service: AIServiceInterface = Depends(get_ai_service),
) -> Any:
    """Check status of AI/NLP processing pipeline for a document."""
    status_resp = await ai_service.get_processing_status(document_id)
    return status_resp
