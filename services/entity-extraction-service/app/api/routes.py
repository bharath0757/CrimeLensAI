"""
Extraction Service — API Routes
================================
Endpoints for entity extraction and resolution from raw case text.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

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


@router.post("/extract", response_model=ExtractionResponse)
async def extract_entities(payload: ExtractionRequest):
    """
    Extract entities from raw text input.

    Accepts FIR text, call record transcripts, or financial transaction logs.
    Returns extracted entities with:
    - entity_type: PERSON | PHONE | VEHICLE | UPI_ID | LOCATION | ORG | DATE
    - value: the extracted text
    - normalized_value: canonical normalized form
    - confidence: 0.0–1.0 confidence score
    - start_offset / end_offset: character positions in source text
    - source_field: which input field the entity was found in
    """
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Input text must not be empty.")

    try:
        entities = run_extraction(
            text=payload.text,  # use original text for accurate offsets
            source_field=payload.source_type.value,
            case_id=payload.case_id,
        )
    except RuntimeError as exc:
        # spaCy model unavailable or other pipeline errors
        logger.exception("Extraction pipeline error")
        raise HTTPException(
            status_code=503,
            detail=f"Extraction pipeline unavailable: {exc}",
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected extraction error")
        raise HTTPException(
            status_code=500,
            detail=f"Extraction failed: {exc}",
        ) from exc

    return ExtractionResponse(status="ok", entities=entities)


@router.post("/resolve", response_model=ResolutionResponse)
async def resolve_entities_endpoint(payload: ResolutionRequest):
    """
    Fuzzy-match and resolve entity variants across cases.

    Given a list of extracted entities, groups them by likely identity
    (e.g., "Rajesh Kumar", "R. Kumar", "Rajesh K." → same person).

    Uses exact matching for deterministic types (PHONE, VEHICLE, UPI_ID)
    and RapidFuzz for fuzzy types (PERSON, ORG, LOCATION).
    """
    try:
        groups = resolve_entities(payload.entities)
    except Exception as exc:
        logger.exception("Resolution error")
        raise HTTPException(
            status_code=500,
            detail=f"Entity resolution failed: {exc}",
        ) from exc

    return ResolutionResponse(status="ok", resolved_groups=groups)
