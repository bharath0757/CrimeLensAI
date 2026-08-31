from fastapi import APIRouter

from app.api.v1.endpoints import (
    health,
    auth,
    documents,
    entities,
    relationships,
    graph,
    ledger,
)
from app.api.routes import router as canonical_router

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(documents.router, tags=["Document Management"])
api_router.include_router(entities.router, tags=["Entities"])
api_router.include_router(relationships.router, tags=["Relationship Management"])
api_router.include_router(graph.router, tags=["Graph & Network Analysis"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["Ledger Audit Trail"])

# Include the canonical implementation for Cases, Entities, Search, and Dashboard
api_router.include_router(canonical_router)
