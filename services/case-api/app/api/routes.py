"""
API Service — Routes
=====================
Public Case API endpoints with real CRUD, NLP orchestration,
and dashboard statistics.

Orchestration flow for POST /api/v1/cases:
  1. Create case in in-memory repository
  2. If fir_text provided → call NLP extract_entities
  3. Save extracted entities in entity repository
  4. Attempt graph ingestion (upsert each entity)
  5. Update case status based on results
  6. Return case with entities and processing notes

All downstream service failures are handled gracefully:
the case is always created and returned.
"""

from __future__ import annotations

import logging
from typing import Any, Optional
import httpx

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

from app.integrations.ai_integration import AIServiceBase, get_ai_service
from app.integrations.graph_integration import GraphServiceBase, get_graph_service
from app.repositories.case_repository import CaseRepository
from app.repositories.entity_repository import EntityRepository
from app.schemas.case import (
    CaseCreate,
    CaseResponse,
    CaseUpdate,
    DashboardStats,
)
from app.schemas.entity import ExtractedEntity

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["Cases"])

# ── Dependency singletons ─────────────────────────────────
case_repo = CaseRepository()
entity_repo = EntityRepository()
ai_service: AIServiceBase = get_ai_service()
graph_service: GraphServiceBase = get_graph_service()


# ── Cases CRUD ────────────────────────────────────────────

@router.post("/cases", response_model=CaseResponse, status_code=201)
async def create_case(payload: CaseCreate) -> CaseResponse:
    """
    Create a new case and trigger the NLP extraction pipeline.

    Orchestration:
      1. Persist case (status=DRAFT)
      2. Call NLP service extract_entities on fir_text
      3. Persist extracted entities
      4. Call Graph service upsert_entity for each entity
      5. Update case status to PROCESSING / ACTIVE
    """
    # Step 1: create case
    case = case_repo.create(payload)
    notes: list[str] = []

    # Step 2: NLP extraction (if text available)
    extracted_entities: list[ExtractedEntity] = []
    text_to_extract = payload.fir_text or ""

    if text_to_extract.strip():
        try:
            nlp_result = await ai_service.extract_entities(
                text_to_extract, "fir_text"
            )
            raw_entities = nlp_result.get("entities", [])
            extracted_entities = [
                ExtractedEntity(
                    **e,
                    case_id=case.id,
                )
                if isinstance(e, dict) else e
                for e in raw_entities
            ]
            notes.append(f"NLP: extracted {len(extracted_entities)} entities")
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            url = str(exc.request.url)
            body = exc.response.text[:1000]
            logger.warning("NLP extraction failed for case %s: %s %s - %s", case.id, status, url, body)
            notes.append(f"NLP: extraction failed (HTTPStatusError: {status} {url} - {body})")
        except Exception as exc:
            logger.warning("NLP extraction failed for case %s: %s", case.id, exc)
            notes.append(f"NLP: extraction failed ({type(exc).__name__})")

    # Step 3: persist entities
    if extracted_entities:
        entity_repo.save(case.id, extracted_entities)
        case_repo.update_field(
            case.id,
            entities=[e.model_dump() for e in extracted_entities],
            status="PROCESSING",
        )
        notes.append("Entities saved")

    # Step 4: graph ingestion (best-effort)
    if extracted_entities:
        try:
            for ent in extracted_entities:
                await graph_service.upsert_entity(ent.model_dump())
            notes.append(f"Graph: ingested {len(extracted_entities)} entities")
            case_repo.update_field(case.id, status="ACTIVE")
        except Exception as exc:
            logger.warning(
                "Graph ingestion failed for case %s: %s", case.id, exc
            )
            notes.append(f"Graph: ingestion failed ({type(exc).__name__})")

    # Step 5: set processing notes
    processing_notes = "; ".join(notes) if notes else None
    case_repo.update_field(case.id, processing_notes=processing_notes)

    # Return fresh state
    final = case_repo.get(case.id)
    return final  # type: ignore[return-value]


@router.get("/cases", response_model=list[CaseResponse])
async def list_cases(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
) -> list[CaseResponse]:
    """List all cases with pagination."""
    return case_repo.list_all(skip=skip, limit=limit)


@router.get("/cases/{case_id}", response_model=CaseResponse)
async def get_case(case_id: str) -> CaseResponse:
    """
    Get a single case by ID, including extracted entities.

    Entities from the entity repository are merged into the response.
    Graph service failures are silently ignored.
    """
    case = case_repo.get(case_id)
    if case is None:
        raise HTTPException(status_code=404, detail="Case not found")

    # Merge entities from entity repo if case record entities are empty
    if not case.entities:
        stored_entities = entity_repo.get(case_id)
        if stored_entities:
            case_repo.update_field(
                case_id,
                entities=[e.model_dump() for e in stored_entities],
            )
            case = case_repo.get(case_id)  # type: ignore[assignment]

    return case  # type: ignore[return-value]


@router.put("/cases/{case_id}", response_model=CaseResponse)
async def update_case(case_id: str, payload: CaseUpdate) -> CaseResponse:
    """Update case metadata."""
    result = case_repo.update(case_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="Case not found")
    return result


@router.delete("/cases/{case_id}", status_code=200)
async def delete_case(case_id: str):
    """
    Soft-delete a case (mark as ARCHIVED).
    Uses 200 with body rather than 204 for consistency with OpenAPI contract.
    """
    if not case_repo.delete(case_id):
        raise HTTPException(status_code=404, detail="Case not found")
    return {"case_id": case_id, "status": "ARCHIVED", "message": "Case archived"}


# ── Search ────────────────────────────────────────────────

@router.get("/search")
async def search(
    q: str = Query(..., min_length=1),
    entity_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """
    Full-text search across cases and entities.

    Searches case titles, FIR text, districts, stations, and entity values.
    Optionally filters entities by entity_type.
    """
    case_results = case_repo.search(q, skip=skip, limit=limit)
    entity_results = entity_repo.search(q)

    # Filter entities by type if requested
    if entity_type:
        entity_results = [
            e for e in entity_results if e.entity_type == entity_type
        ]

    return {
        "query": q,
        "cases": [c.model_dump() for c in case_results],
        "entities": [e.model_dump() for e in entity_results[:limit]],
        "total_cases": len(case_results),
        "total_entities": len(entity_results),
    }


# ── Ingestion (placeholder — out of scope for this task) ──

@router.post("/ingest")
async def ingest_data(payload: dict):
    """
    Bulk ingestion endpoint for batch data loading.
    Not implemented in this task per requirements.
    """
    return {"status": "ok", "message": "Ingestion placeholder", "records_queued": 0}


# ── Dashboard ─────────────────────────────────────────────

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats() -> DashboardStats:
    """Aggregated statistics for the investigator dashboard."""
    return DashboardStats(
        total_cases=case_repo.count(),
        total_entities=entity_repo.count(),
        cross_case_links=0,  # Graph placeholder not yet wired
        pending_reviews=0,
        cases_by_status=case_repo.count_by_status(),
    )


# ── Entity Actions (placeholders — out of scope) ─────────

@router.post("/entities/{entity_id}/confirm")
async def confirm_entity(entity_id: str):
    """Confirm an extracted entity. Placeholder for ledger integration."""
    return {"entity_id": entity_id, "message": "Entity confirmation placeholder"}


@router.post("/entities/{entity_id}/reject")
async def reject_entity(entity_id: str):
    """Reject an extracted entity. Placeholder for ledger integration."""
    return {"entity_id": entity_id, "message": "Entity rejection placeholder"}


@router.get("/diagnostics/nlp")
async def check_nlp_connection():
    """
    Diagnostic endpoint to verify AI_SERVICE_URL + /api/v1/extract
    Uses the exact HTTPAIService logic to test the connection and report details.
    """
    from app.core.config import settings
    url = settings.ai_service_url.rstrip("/") + "/api/v1/extract"
    payload = {"text": "Diagnostic test", "source_type": "fir_text"}
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(url, json=payload, timeout=5.0)
            return {
                "configured_url": settings.ai_service_url,
                "tested_url": url,
                "status_code": resp.status_code,
                "response_body": resp.text[:1000]
            }
    except Exception as exc:
        return {
            "configured_url": settings.ai_service_url,
            "tested_url": url,
            "error_type": type(exc).__name__,
            "error_msg": str(exc)
        }
