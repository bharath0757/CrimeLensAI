"""
CrimeLensAI — Ledger Service
==============================
FastAPI microservice for tamper-evident audit logging and access control.

Responsibilities:
- Hash-chain tamper-evidence ledger: every entity/relationship write from
  other services gets SHA-256 hashed and appended to an append-only chain.
- verify(record_id) endpoint to prove a record has not been altered.
- JWT-based authentication with role-based access control:
  Investigator / Supervisor / Admin roles.
- Field-level privacy masking for victim-identifying data.

Part of the AI-Powered Criminal Network Analysis System (SIH 2026).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="CrimeLensAI — Ledger Service",
    description=(
        "Hash-chain tamper-evidence ledger and authentication service. "
        "Every entity and relationship write is hashed and appended to an "
        "append-only chain. Provides JWT auth, RBAC, and field-level "
        "privacy masking for victim-identifying data."
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
    """Health check endpoint for container orchestration and monitoring."""
    return {
        "status": "healthy",
        "service": "ledger",
        "version": "0.1.0",
    }
