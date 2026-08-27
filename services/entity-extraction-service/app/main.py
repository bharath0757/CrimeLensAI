"""
CrimeLensAI — Extraction Service
=================================
FastAPI microservice for NLP-based entity extraction from case data.

Extracts entities (PERSON, PHONE, VEHICLE, UPI_ID, LOCATION, ORG, DATE)
using spaCy NER + regex pipelines with confidence scores and source offsets.
Includes fuzzy-matching / entity-resolution layer for name variants.

Part of the AI-Powered Criminal Network Analysis System (SIH 2026).
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.core.nlp import load_model

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CrimeLensAI — Extraction Service",
    description=(
        "NLP entity extraction microservice. Extracts PERSON, PHONE, VEHICLE, "
        "UPI_ID, LOCATION, ORG, DATE entities from FIR text, call records, and "
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

# Track whether the spaCy model loaded successfully
_model_healthy = False


@app.on_event("startup")
async def startup_load_model():
    """Pre-load the spaCy model at application startup."""
    global _model_healthy  # noqa: PLW0603
    try:
        load_model()
        _model_healthy = True
        logger.info("Extraction service ready.")
    except RuntimeError:
        _model_healthy = False
        logger.error(
            "spaCy model failed to load. "
            "The service will start but /extract will return 503."
        )


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container orchestration and monitoring."""
    return {
        "status": "healthy" if _model_healthy else "degraded",
        "service": "extraction",
        "version": "0.1.0",
        "spacy_model_loaded": _model_healthy,
    }
