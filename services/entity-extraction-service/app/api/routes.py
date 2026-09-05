"""Extraction service API routes."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from starlette.concurrency import run_in_threadpool

from app.core.nlp import loaded_model_name
from app.extractors.pipeline import run_extraction
from app.extractors.resolver import resolve_entities
from app.models.schemas import (
    BatchExtractionRequest,
    BatchExtractionResponse,
    ExtractionRequest,
    ExtractionResponse,
    FirExtractionResult,
    ResolutionRequest,
    ResolutionResponse,
)
from app.security import require_service_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Extraction"], dependencies=[Depends(require_service_token)])


def _model_metadata() -> dict:
    model = loaded_model_name()
    warnings = ["Confidence scores are heuristic, not calibrated identity probabilities. Review all extracted mentions."]
    if model == "blank_en_fallback":
        warnings.append("Statistical NER model unavailable: contextual name, location and organization coverage is limited.")
    return {"model": model, "warnings": warnings}


@router.post("/extract", response_model=ExtractionResponse, status_code=status.HTTP_200_OK)
def extract_entities(payload: ExtractionRequest) -> ExtractionResponse:
    """Extract normalized entities with confidence and source offsets."""
    if not payload.text.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Input text must not be blank.",
        )
    try:
        entities = run_extraction(
            text=payload.text,
            source_field=payload.source_field or payload.source_type.value,
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

    return ExtractionResponse(status="ok", entities=entities, **_model_metadata())


@router.post(
    "/extract/batch",
    response_model=BatchExtractionResponse,
    status_code=status.HTTP_200_OK,
)
async def extract_fir_batch(payload: BatchExtractionRequest) -> BatchExtractionResponse:
    """Extract a bounded FIR batch while retaining per-case provenance."""
    results: list[FirExtractionResult] = []
    for fir in payload.firs:
        extraction = await run_in_threadpool(
            extract_entities,
            ExtractionRequest(text=fir.raw_text, source_field=fir.source_field, case_id=fir.case_id),
        )
        results.append(
            FirExtractionResult(
                case_id=fir.case_id,
                district=fir.district,
                fir_number=fir.fir_number,
                entities=extraction.entities,
                model=extraction.model,
                warnings=extraction.warnings,
            )
        )
    return BatchExtractionResponse(
        cases_processed=len(results),
        entities_extracted=sum(len(item.entities) for item in results),
        results=results,
    )


@router.post("/resolve", response_model=ResolutionResponse, status_code=status.HTTP_200_OK)
def resolve_entities_endpoint(payload: ResolutionRequest) -> ResolutionResponse:
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
