"""
Extraction Service - API Routes
================================
Endpoints for entity extraction from raw case text.
"""

from fastapi import APIRouter
from app.services.extractor import extract_entities_from_text

router = APIRouter(prefix="/api/v1", tags=["Extraction"])

@router.post("/extract")
async def extract_entities(payload: dict):
    """
    Extract entities from raw text input.
    """
    text = payload.get("text", "")
    source_field = payload.get("source_field", "fir_text")
    
    entities = extract_entities_from_text(text, source_field)
    
    return {
        "status": "ok",
        "message": "Extracted entities successfully",
        "entities": entities,
    }

@router.post("/resolve")
async def resolve_entities(payload: dict):
    """
    Fuzzy-match and resolve entity variants across cases.
    """
    return {
        "status": "ok",
        "message": "Entity resolution endpoint placeholder",
        "resolved_groups": [],
    }
