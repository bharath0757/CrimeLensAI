"""
CrimeLensAI — API Service (Orchestration Layer)
=================================================
The public-facing Case API and orchestration gateway.

Responsibilities:
- Case CRUD (create, read, update, delete cases)
- Search across cases and entities
- Ingestion validation (clean and validate incoming data before extraction)
- Aggregation calls across extraction, graph, and ledger services
- PostgreSQL datastore for cases, entities, and users tables

This is the only service the frontend talks to directly.
All cross-service coordination flows through here.

Part of the AI-Powered Criminal Network Analysis System (SIH 2026).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="CrimeLensAI — API Gateway",
    description=(
        "Orchestration layer and public Case API. Handles case CRUD, search, "
        "ingestion validation, and coordinates calls to extraction, graph, "
        "and ledger services. PostgreSQL-backed."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Also reports connectivity to downstream services and PostgreSQL.
    """
    # TODO: Add actual health checks for Postgres + downstream services
    return {
        "status": "healthy",
        "service": "api",
        "version": "0.1.0",
        "dependencies": {
            "postgres": "not_checked",
            "extraction": "not_checked",
            "graph": "not_checked",
            "ledger": "not_checked",
        },
    }
