"""
CrimeLensAI — spaCy Model Loader
==================================
Loads the configured spaCy pipeline once. If the optional statistical model
is unavailable, the service keeps operating with a blank English pipeline;
the deterministic FIR extractors still cover structured and contextual data.
"""

from __future__ import annotations

import logging

import spacy
from spacy.language import Language

from app.core.config import settings

logger = logging.getLogger(__name__)

_nlp_instance: Language | None = None
_model_name_loaded = "not_loaded"


def load_model() -> Language:
    """Load the spaCy model specified by ``SPACY_MODEL`` env var.

    Raises
    ------
    RuntimeError
        If the model cannot be loaded (not installed, corrupt, etc.).
    """
    global _nlp_instance, _model_name_loaded
    model_name = settings.SPACY_MODEL
    try:
        logger.info("Loading spaCy model '%s' ...", model_name)
        _nlp_instance = spacy.load(model_name)
        _model_name_loaded = model_name
        logger.info("spaCy model '%s' loaded successfully.", model_name)
        return _nlp_instance
    except OSError:
        logger.warning(
            "spaCy model '%s' is unavailable; using deterministic extraction fallback.",
            model_name,
        )
        _nlp_instance = spacy.blank("en")
        _model_name_loaded = "blank_en_fallback"
        return _nlp_instance


def get_nlp() -> Language:
    """Return the cached spaCy ``Language`` pipeline.

    The model is loaded on first call and reused thereafter.
    """
    if _nlp_instance is None:
        load_model()
    assert _nlp_instance is not None  # for type-checker
    return _nlp_instance


def loaded_model_name() -> str:
    """Return the active statistical model or fallback identifier."""
    return _model_name_loaded
