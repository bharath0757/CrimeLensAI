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
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as api_router
from app.core.nlp import load_model, loaded_model_name

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Track the optional statistical NER model without disabling deterministic extraction.
_model_healthy = False


@asynccontextmanager
async def lifespan(_application: FastAPI):
    """Pre-load the spaCy model at application startup."""
    global _model_healthy
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and len(
        os.getenv("SERVICE_AUTH_TOKEN", "").encode()
    ) < 32:
        raise RuntimeError("Production extraction service requires a 32-byte service token")
    try:
        load_model()
        _model_healthy = True
        logger.info("Extraction service ready.")
    except Exception:
        _model_healthy = False
        logger.exception("NLP initialization failed")
    yield


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
    lifespan=lifespan,
)

app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for container orchestration and monitoring."""
    return {
        "status": "healthy" if _model_healthy else "degraded",
        "service": "extraction",
        "version": "0.1.0",
        "spacy_model_loaded": loaded_model_name() not in {"not_loaded", "blank_en_fallback"},
        "nlp_backend": loaded_model_name(),
        "deterministic_extractors": "ready",
    }
