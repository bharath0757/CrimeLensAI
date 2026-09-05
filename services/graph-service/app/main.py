"""CrimeLensAI — Graph Service"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException

from app.api.batches import router as batch_router
from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.neo4j import neo4j_manager

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup/shutdown lifecycle for Neo4j connection."""
    settings = get_settings()
    if settings.GRAPH_BACKEND.lower() == "neo4j":
        try:
            neo4j_manager.connect()
            logger.info("Neo4j connected at %s", settings.NEO4J_URI)
            from app.api.routes import store
            if hasattr(store, "hydrate"):
                store.hydrate()
        except Exception:
            neo4j_manager.close()
            logger.exception("Neo4j startup failed; graph service cannot accept writes")
            raise
    yield
    if settings.GRAPH_BACKEND.lower() == "neo4j":
        neo4j_manager.close()
        logger.info("Neo4j connection closed")


app = FastAPI(
    title="CrimeLensAI — Graph Service",
    description=(
        "Neo4j-backed graph analysis microservice. Provides cross-case linkage, "
        "centrality, community detection, and shortest-path queries with "
        "human-readable explanations for every discovered relationship."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.include_router(api_router)
app.include_router(batch_router)

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check with Neo4j connectivity verification."""
    settings = get_settings()
    from app.api.routes import store

    neo4j_status = "not_configured"
    if settings.GRAPH_BACKEND.lower() == "neo4j":
        connected = neo4j_manager.verify_connectivity()
        neo4j_status = "connected" if connected else "unavailable"

    if neo4j_status == "unavailable":
        raise HTTPException(503, "Neo4j unavailable")
    overall = "healthy"

    return {
        "status": overall,
        "service": settings.SERVICE_NAME,
        "version": settings.SERVICE_VERSION,
        "neo4j": neo4j_status,
        "backend": store.__class__.__name__,
    }
