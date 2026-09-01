"""
CrimeLensAI — Graph Service
============================
FastAPI microservice wrapping Neo4j for cross-case linkage analysis.

Provides Cypher-backed endpoints for:
- Cross-case entity linkage (shared suspects, vehicles, phone numbers)
- Centrality analysis (identifying key nodes in criminal networks)
- Community detection (clustering related cases/entities)
- Shortest-path queries (how two entities are connected)
- Human-readable "why linked" explanations for every relationship

Part of the AI-Powered Criminal Network Analysis System (SIH 2026).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

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
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)

@app.on_event("startup")
async def startup_event():
    from app.core.database import driver
    async with driver.session() as session:
        # Priority 1 constraint for duplicate entity resolution
        await session.run("CREATE CONSTRAINT entity_identity IF NOT EXISTS FOR (e:Entity) REQUIRE (e.name, e.type) IS UNIQUE")
        # Ensure Case ID constraint
        await session.run("CREATE CONSTRAINT case_identity IF NOT EXISTS FOR (c:Case) REQUIRE c.id IS UNIQUE")

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint. Also verifies Neo4j connectivity."""
    # TODO: Add actual Neo4j ping check
    return {
        "status": "healthy",
        "service": "graph",
        "version": "0.1.0",
        "neo4j": "not_checked",
    }
