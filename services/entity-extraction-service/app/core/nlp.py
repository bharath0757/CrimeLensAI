"""
CrimeLensAI — spaCy Model Loader
==================================
Loads the spaCy NLP model once and exposes it via ``get_nlp()``.

The model is loaded lazily on first access and cached for the
lifetime of the process.  If the model is unavailable, a clear
``RuntimeError`` is raised at load time rather than failing
silently on every request.
"""

from __future__ import annotations

import logging
from typing import Optional

import spacy
from spacy.language import Language

from app.core.config import settings

logger = logging.getLogger(__name__)

_nlp_instance: Optional[Language] = None


def load_model() -> Language:
    """Load the spaCy model specified by ``SPACY_MODEL`` env var.

    Raises
    ------
    RuntimeError
        If the model cannot be loaded (not installed, corrupt, etc.).
    """
    global _nlp_instance  # noqa: PLW0603
    model_name = settings.SPACY_MODEL
    try:
        logger.info("Loading spaCy model '%s' ...", model_name)
        _nlp_instance = spacy.load(model_name)
        logger.info("spaCy model '%s' loaded successfully.", model_name)
        return _nlp_instance
    except OSError as exc:
        msg = (
            f"spaCy model '{model_name}' is not installed. "
            f"Install it with: python -m spacy download {model_name}"
        )
        logger.error(msg)
        raise RuntimeError(msg) from exc


def get_nlp() -> Language:
    """Return the cached spaCy ``Language`` pipeline.

    The model is loaded on first call and reused thereafter.
    """
    global _nlp_instance  # noqa: PLW0603
    if _nlp_instance is None:
        load_model()
    assert _nlp_instance is not None  # for type-checker
    return _nlp_instance
