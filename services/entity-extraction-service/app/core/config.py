"""
CrimeLensAI — Extraction Service Configuration
================================================
Environment-driven settings for the extraction service.
"""

import os


class Settings:
    """Application settings loaded from environment variables."""

    # spaCy model to use for NER
    SPACY_MODEL: str = os.getenv("SPACY_MODEL", "en_core_web_sm")

    # Confidence scores for regex-based extraction (deterministic)
    CONFIDENCE_REGEX: float = float(os.getenv("CONFIDENCE_REGEX", "0.95"))

    # Floor confidence for spaCy NER when model score is unavailable
    CONFIDENCE_SPACY_FLOOR: float = float(os.getenv("CONFIDENCE_SPACY_FLOOR", "0.70"))

    # RapidFuzz threshold for fuzzy entity resolution (0-100)
    RESOLUTION_FUZZY_THRESHOLD: float = float(os.getenv("RESOLUTION_FUZZY_THRESHOLD", "80"))


settings = Settings()
