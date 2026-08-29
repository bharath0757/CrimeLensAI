"""
Extraction Service — API Routes
================================
Endpoints for entity extraction and resolution from raw case text.
"""

from fastapi import APIRouter

from app.extractors.nlp_pipeline import extract_entities as run_extraction
from app.extractors.resolver import resolve_entities as run_resolution
from app.models.schemas import (
    ExtractionRequest,
    ExtractionResponse,
    ResolutionRequest,
    ResolutionResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Extraction"])


@router.post("/extract", response_model=ExtractionResponse)
async def extract_entities(request: ExtractionRequest) -> ExtractionResponse:
    """
    Extract entities from raw text input.

    Accepts FIR text, call record transcripts, or financial transaction logs.
    Returns extracted entities with:
    - entity_type: PERSON | PHONE | VEHICLE | UPI_ID | LOCATION | ORG
    - value: the extracted text
    - confidence: 0.0–1.0 confidence score
    - start_offset / end_offset: character positions in source text
    - source_field: which input field the entity was found in
    """
    entities = run_extraction(request.text, request.source_type)
    return ExtractionResponse(status="ok", entities=entities)


@router.post("/resolve", response_model=ResolutionResponse)
async def resolve_entities(request: ResolutionRequest) -> ResolutionResponse:
    """
    Fuzzy-match and resolve entity variants across cases.

    Given a list of extracted entities, groups them by likely identity
    (e.g., "Rajesh Kumar", "R. Kumar", "Rajesh K." → same person).
    """
    groups = run_resolution(request.entities)
    return ResolutionResponse(status="ok", resolved_groups=groups)
