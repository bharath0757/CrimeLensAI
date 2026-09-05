"""Authenticated previews use the same extractor as persisted evidence."""

import asyncio
import logging
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from app.api.deps import get_ai_service, get_current_user
from app.core.config import settings
from app.integrations.ai_integration import AIServiceInterface, ExtractionResult
from app.schemas.user import UserResponse
from app.services.document_text import (
    MAX_TEXT_CHARACTERS,
    DocumentTextError,
    decode_document,
)

router = APIRouter()
logger = logging.getLogger(__name__)
CurrentUser = Annotated[UserResponse, Depends(get_current_user)]
AIService = Annotated[AIServiceInterface, Depends(get_ai_service)]


class PreviewRequest(BaseModel):
    text: str = Field(min_length=1, max_length=MAX_TEXT_CHARACTERS)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Provide readable FIR text.")
        return value


class PreviewResponse(ExtractionResult):
    text: str
    document_sha256: str | None = None


async def _preview(text: str, ai_service: AIServiceInterface, sha256: str | None = None) -> PreviewResponse:
    try:
        result = await ai_service.extract_text(text)
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Extraction preview failed: error_type=%s", type(exc).__name__)
        raise HTTPException(503, "Extraction service unavailable or returned invalid results. Retry shortly.") from exc
    return PreviewResponse(**result.model_dump(), text=text, document_sha256=sha256)


@router.post("/extraction/preview", response_model=PreviewResponse)
async def preview_text(body: PreviewRequest, current_user: CurrentUser, ai_service: AIService):
    """Extract review candidates without creating a case, graph node or document."""
    return await _preview(body.text, ai_service)


@router.post("/extraction/preview-file", response_model=PreviewResponse)
async def preview_file(
    file: Annotated[UploadFile, File()], current_user: CurrentUser, ai_service: AIService,
):
    """Read a text-based FIR; source offsets refer to the returned converted text."""
    raw = await file.read(settings.MAX_FILE_SIZE_BYTES + 1)
    if len(raw) > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(413, "Document exceeds the upload size limit.")
    try:
        source = await asyncio.to_thread(decode_document, raw, Path(file.filename or "").suffix)
    except DocumentTextError as exc:
        raise HTTPException(422, str(exc)) from exc
    return await _preview(source.text, ai_service, source.sha256)
