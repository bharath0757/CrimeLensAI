"""
CrimeLensAI — spaCy NER Extractor
====================================
Wraps spaCy NER to extract PERSON, ORG, LOCATION (GPE/LOC), and DATE
entities from raw text.

Confidence scoring strategy:
  - spaCy 3.x ``en_core_web_sm`` does not expose per-entity confidence
    scores.  We assign a deterministic floor score from config
    (default 0.70) for all model-based entities.
  - This is documented and predictable — no random values.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.config import settings
from app.core.nlp import get_nlp
from app.extractors.regex_extractors import RawMatch

if TYPE_CHECKING:
    from spacy.tokens import Doc

# Mapping from spaCy NER labels to our entity types
_LABEL_MAP: dict[str, str] = {
    "PERSON": "PERSON",
    "ORG": "ORG",
    "GPE": "LOCATION",
    "LOC": "LOCATION",
    "DATE": "DATE",
}


def extract_spacy_entities(text: str) -> list[RawMatch]:
    """Run spaCy NER on *text* and return mapped entity matches.

    Only labels present in ``_LABEL_MAP`` are returned.  Character
    offsets refer to the original *text*.
    """
    nlp = get_nlp()
    doc: Doc = nlp(text)

    matches: list[RawMatch] = []
    for ent in doc.ents:
        mapped_type = _LABEL_MAP.get(ent.label_)
        if mapped_type is None:
            continue

        matches.append(
            RawMatch(
                entity_type=mapped_type,
                value=ent.text,
                start_offset=ent.start_char,
                end_offset=ent.end_char,
                confidence=settings.CONFIDENCE_SPACY_FLOOR,
            )
        )

    return matches
