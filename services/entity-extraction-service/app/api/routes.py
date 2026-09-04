"""Extraction service API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, status

from app.extractors.pipeline import run_extraction
from app.extractors.resolver import resolve_entities
from app.models.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    ResolutionRequest,
    ResolutionResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Extraction"])


@router.post("/extract", response_model=ExtractionResponse, status_code=status.HTTP_200_OK)
async def extract_entities(payload: ExtractionRequest) -> ExtractionResponse:
    """Extract normalized entities with confidence and source offsets."""
    try:
        entities = run_extraction(
            text=payload.text,
            source_field=payload.source_type.value,
            case_id=payload.case_id,
        )
    except RuntimeError as exc:
        logger.exception("Extraction pipeline unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Extraction pipeline is temporarily unavailable.",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected extraction failure")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Entity extraction failed.",
        ) from exc

    return ExtractionResponse(status="ok", entities=entities)


@router.post("/resolve", response_model=ResolutionResponse, status_code=status.HTTP_200_OK)
async def resolve_entities_endpoint(payload: ResolutionRequest) -> ResolutionResponse:
    """Resolve likely aliases while preserving every original mention."""
    try:
        groups = resolve_entities(payload.entities)
    except Exception as exc:
        logger.exception("Entity resolution failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Entity resolution failed.",
        ) from exc

    return ResolutionResponse(status="ok", resolved_groups=groups)
