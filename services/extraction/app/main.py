"""
CrimeLensAI — Extraction Service
=================================
FastAPI microservice for NLP-based entity extraction from case data.

Extracts entities (PERSON, PHONE, VEHICLE, UPI_ID, LOCATION, ORG) using
spaCy NER + regex pipelines with confidence scores and source offsets.
Includes fuzzy-matching / entity-resolution layer for name variants.

Part of the AI-Powered Criminal Network Analysis System (SIH 2026).
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router

app = FastAPI(
    title="CrimeLensAI — Extraction Service",
    description=(
        "NLP entity extraction microservice. Extracts PERSON, PHONE, VEHICLE, "
        "UPI_ID, LOCATION, ORG entities from FIR text, call records, and "
        "financial transaction logs with confidence scores and source offsets."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow frontend and API gateway to call this service
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Lock down in production
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
        "service": "extraction",
        "version": "0.1.0",
    }
