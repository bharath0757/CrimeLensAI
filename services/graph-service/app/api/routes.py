"""
Graph Service — API Routes
============================
Endpoints for Neo4j-backed graph queries and analysis.
"""

from fastapi import APIRouter, HTTPException, Query

from app.analysis import FirAnalysisService
from app.models import AlertStatus, EntityInput, FirAnalysisRequest, RelationshipInput
from app.store import build_store

router = APIRouter(prefix="/api/v1", tags=["Graph"])
store = build_store()
fir_analysis_service = FirAnalysisService(store)


@router.post("/entities")
def upsert_entity(payload: EntityInput):
    """
    Create or update an entity node in the graph.

    Entity types: PERSON, PHONE, VEHICLE, UPI_ID, LOCATION, ORG
    Each node is linked to its source case(s).

    If the normalized entity already appears in another case, this operation
    also creates or updates an officer-facing cross-case alert.
    """
    return store.upsert_entity(payload)


@router.post("/relationships")
def create_relationship(payload: RelationshipInput):
    """
    Create a relationship between two entity nodes.

    Every relationship includes:
    - relationship_type (e.g., CONTACTED, TRANSACTED, CO_LOCATED)
    - source_case_id: the case that evidences this relationship
    - confidence: extraction confidence score
    - why_linked: human-readable explanation

    """
    try:
        return {"relationship": store.create_relationship(payload)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/linkage/{case_id}")
def get_cross_case_linkage(case_id: str):
    """
    Find all cases linked to the given case through shared entities.

    Returns a subgraph of connected cases with:
    - The shared entity (name, type)
    - The linking path
    - A human-readable "why linked" explanation

    """
    return store.get_linkage(case_id)


@router.get("/centrality/{entity_id}")
def get_entity_centrality(entity_id: str):
    """
    Compute centrality metrics for an entity node.

    Returns degree, betweenness, and PageRank centrality to identify
    key nodes (e.g., a phone number that appears in 15 cases).

    """
    try:
        return store.centrality(entity_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/communities")
def detect_communities():
    """
    Run community detection on the entity graph.

    Groups entities into clusters that likely represent the same
    criminal network or operation.

    """
    return store.communities()


@router.get("/shortest-path")
def shortest_path(entity_a: str, entity_b: str):
    """
    Find the shortest path between two entities in the graph.

    Returns the path with all intermediate nodes and relationships,
    plus a human-readable narrative explaining the connection.

    """
    try:
        return store.shortest_path(entity_a, entity_b)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
def list_alerts(case_id: str | None = None, status: AlertStatus | None = None):
    """List cross-case connection alerts for an officer's queue."""
    return {"alerts": store.list_alerts(case_id=case_id, status=status.value if status else None)}


@router.post("/alerts/{alert_id}/acknowledge")
def acknowledge_alert(alert_id: str):
    """Mark an alert as seen without erasing its evidence or history."""
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
