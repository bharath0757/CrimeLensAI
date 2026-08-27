"""Graph Service — API Routes"""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.analysis import FirAnalysisService
from app.models import AlertStatus, EntityInput, FirAnalysisRequest, RelationshipInput
from app.models.schemas import (
    EntityUpsertRequest, RelationshipCreateRequest,
)
from app.services.graph_service import GraphService
from app.services.analytics_service import AnalyticsService
from app.store import build_store

router = APIRouter(prefix="/api/v1", tags=["Graph"])
store = build_store()
graph_service = GraphService(store)
analytics_service = AnalyticsService(store)
fir_analysis_service = FirAnalysisService(store)


@router.post("/entities")
def upsert_entity(payload: EntityUpsertRequest):
    """Create or update an entity node in the graph."""
    result = graph_service.upsert_entity(payload)
    return result.model_dump()


@router.post("/relationships")
def create_relationship(payload: RelationshipCreateRequest):
    """Create a relationship between two entity nodes."""
    try:
        result = graph_service.create_relationship(payload)
        return result.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/linkage/{case_id}")
def get_cross_case_linkage(case_id: str):
    """Find all cases linked through shared entities."""
    result = graph_service.get_linkage(case_id)
    return result.model_dump()


@router.get("/centrality/{entity_id}")
def get_entity_centrality(entity_id: str):
    """Compute centrality metrics for an entity."""
    try:
        result = analytics_service.get_centrality(entity_id)
        return result.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/communities")
def detect_communities():
    """Run community detection on the entity graph."""
    result = analytics_service.detect_communities()
    return result.model_dump()


@router.get("/shortest-path")
def shortest_path(entity_a: str, entity_b: str):
    """Find shortest path between two entities."""
    try:
        result = analytics_service.get_shortest_path(entity_a, entity_b)
        return result.model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


# --- Existing endpoints preserved from prior commits ---

@router.get("/patterns/{case_id}")
def detect_case_patterns(case_id: str):
    """Return explainable repeated identifiers, converging signals and bridges."""
    return store.patterns(case_id)


@router.get("/link-predictions")
def predict_missing_links(
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.2, ge=0.0, le=1.0),
):
    """Rank evidence-backed candidate missing links for human review."""
    return store.link_predictions(limit=limit, min_score=min_score)


@router.get("/alerts")
def list_alerts(case_id: Optional[str] = None, status: Optional[AlertStatus] = None):
    """List cross-case connection alerts for an officer's queue."""
    return {"alerts": store.list_alerts(case_id=case_id, status=status.value if status else None)}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    """Mark an alert as seen."""
    try:
        return {"alert": store.acknowledge_alert(alert_id)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/analyze/firs")
def analyze_raw_firs(payload: FirAnalysisRequest):
    """Read raw FIRs, update the graph, and return an officer-ready brief."""
    try:
        return fir_analysis_service.analyze(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
