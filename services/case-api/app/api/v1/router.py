from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    cases,
    dashboard,
    documents,
    entities,
    extraction,
    graph,
    health,
    ingestion,
    ledger,
    relationships,
    reports,
    search,
)

api_router = APIRouter()

api_router.include_router(health.router, tags=["Health"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(cases.router, prefix="/cases", tags=["Case Management"])
api_router.include_router(documents.router, tags=["Document Management"])
api_router.include_router(extraction.router, tags=["Entity Extraction"])
api_router.include_router(ingestion.router, tags=["Structured Evidence"])
api_router.include_router(reports.router, tags=["Evidence Reports"])
api_router.include_router(entities.router, tags=["Entity Management"])
api_router.include_router(relationships.router, tags=["Relationship Management"])
api_router.include_router(graph.router, tags=["Graph & Network Analysis"])
api_router.include_router(search.router, prefix="/search", tags=["Search"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard & Analytics"])
api_router.include_router(ledger.router, prefix="/ledger", tags=["Ledger Audit Trail"])
