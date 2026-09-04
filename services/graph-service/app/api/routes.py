"""Graph service API routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status

from app.analysis import FirAnalysisService
from app.models import AlertStatus, FirAnalysisRequest
from app.models.schemas import EntityUpsertRequest, RelationshipCreateRequest
from app.services.analytics_service import AnalyticsService
from app.services.graph_service import GraphService
from app.store import build_store

router = APIRouter(prefix="/api/v1", tags=["Graph"])
store = build_store()
graph_service = GraphService(store)
analytics_service = AnalyticsService(store)
fir_analysis_service = FirAnalysisService(store)


@router.post("/entities", status_code=status.HTTP_200_OK)
def upsert_entity(payload: EntityUpsertRequest) -> dict:
    """Create or update an entity and attach it to its source case."""
    return graph_service.upsert_entity(payload).model_dump()


@router.post("/relationships", status_code=status.HTTP_201_CREATED)
def create_relationship(payload: RelationshipCreateRequest) -> dict:
    """Create an evidence-backed relationship between graph entities."""
    try:
        return graph_service.create_relationship(payload).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/linkage/{case_id}")
def get_cross_case_linkage(case_id: str) -> dict:
    """Find cases linked by shared evidence and explain every match."""
    return graph_service.get_linkage(case_id).model_dump()


@router.get("/centrality/{entity_id}")
def get_entity_centrality(entity_id: str) -> dict:
    """Calculate degree, betweenness, and closeness centrality."""
    try:
        return analytics_service.get_centrality(entity_id).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.get("/communities")
def detect_communities() -> dict:
    """Detect connected criminal-network communities."""
    return analytics_service.detect_communities().model_dump()


@router.get("/shortest-path")
def shortest_path(entity_a: str, entity_b: str) -> dict:
    """Find and explain the shortest evidence path between two entities."""
    try:
        return analytics_service.get_shortest_path(entity_a, entity_b).model_dump()
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.get("/patterns/{case_id}")
def detect_case_patterns(case_id: str) -> dict:
    """Return repeated identifiers, converging signals, and bridge entities."""
    return store.patterns(case_id)


@router.get("/link-predictions")
def predict_missing_links(
    limit: int = Query(default=20, ge=1, le=100),
    min_score: float = Query(default=0.2, ge=0.0, le=1.0),
) -> dict:
    """Rank evidence-backed candidate links for human review."""
    return store.link_predictions(limit=limit, min_score=min_score)


@router.get("/alerts")
def list_alerts(
    case_id: Optional[str] = None,
    status_filter: Optional[AlertStatus] = Query(default=None, alias="status"),
) -> dict:
    """List cross-case connection alerts for the officer queue."""
    return {
        "alerts": store.list_alerts(
            case_id=case_id,
            status=status_filter.value if status_filter else None,
        )
    }


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str) -> dict:
    """Mark an officer alert as acknowledged."""
    try:
        return {"alert": store.acknowledge_alert(alert_id)}
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/analyze/firs")
def analyze_raw_firs(payload: FirAnalysisRequest) -> dict:
    """Extract raw FIRs, update the graph, and return an officer-ready brief."""
    try:
        return fir_analysis_service.analyze(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
