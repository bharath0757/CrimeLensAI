"""
Extraction Service — API Routes
================================
Endpoints for entity extraction from raw case text.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Extraction"])


@router.post("/extract")
async def extract_entities(payload: dict):
    """
    Extract entities from raw text input.

    Accepts FIR text, call record transcripts, or financial transaction logs.
    Returns extracted entities with:
    - entity_type: PERSON | PHONE | VEHICLE | UPI_ID | LOCATION | ORG
    - value: the extracted text
    - confidence: 0.0–1.0 confidence score
    - start_offset / end_offset: character positions in source text
    - source_field: which input field the entity was found in

    TODO: Wire up spaCy NER pipeline + regex extractors
    """
    return {
        "status": "ok",
        "message": "Extraction endpoint placeholder — wire up spaCy pipeline here",
        "entities": [],
    }


@router.post("/resolve")
async def resolve_entities(payload: dict):
    """
    Fuzzy-match and resolve entity variants across cases.

    Given a list of extracted entities, groups them by likely identity
    (e.g., "Rajesh Kumar", "R. Kumar", "Rajesh K." → same person).

    TODO: Implement fuzzy matching with rapidfuzz / dedupe
    """
    return {
        "status": "ok",
        "message": "Entity resolution endpoint placeholder",
        "resolved_groups": [],
    }
