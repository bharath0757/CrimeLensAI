"""
CrimeLensAI — Extraction Pipeline
====================================
Orchestrates regex + spaCy extraction, deduplicates overlapping
entities, assigns IDs, and normalizes values.

Deduplication strategy:
  When a regex match and a spaCy match overlap in the same span,
  the regex match wins because it is more precise for deterministic
  types (PHONE, VEHICLE, UPI_ID).
"""

from __future__ import annotations

import uuid
from typing import Sequence

from app.extractors.normalizers import normalize
from app.extractors.regex_extractors import RawMatch, run_all_regex
from app.extractors.spacy_extractors import extract_spacy_entities
from app.models.schemas import ExtractedEntityResponse


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Return True if two character spans overlap."""
    return a_start < b_end and b_start < a_end


def _deduplicate(
    regex_matches: list[RawMatch],
    spacy_matches: list[RawMatch],
) -> list[RawMatch]:
    """Merge regex and spaCy matches, preferring regex on overlap.

    For each spaCy match, if it overlaps with any regex match we
    discard the spaCy match.  This prevents double-counting phone
    numbers that spaCy might tag as CARDINAL, etc.
    """
    combined: list[RawMatch] = list(regex_matches)

    for sm in spacy_matches:
        overlaps = any(
            _spans_overlap(sm["start_offset"], sm["end_offset"],
                           rm["start_offset"], rm["end_offset"])
            for rm in regex_matches
        )
        if not overlaps:
            combined.append(sm)

    return combined


def run_extraction(
    text: str,
    source_field: str,
    case_id: str | None = None,
) -> list[ExtractedEntityResponse]:
    """Run the full extraction pipeline on *text*.

    Parameters
    ----------
    text:
        Raw input text to extract entities from.
    source_field:
        Name of the source field (e.g. ``"fir_text"``).
    case_id:
        Optional case identifier for provenance.

    Returns
    -------
    list[ExtractedEntityResponse]
        Deduplicated, normalized entities with stable IDs and offsets
        into the original *text*.
    """
    regex_matches = run_all_regex(text)
    spacy_matches = extract_spacy_entities(text)
    combined = _deduplicate(regex_matches, spacy_matches)

    entities: list[ExtractedEntityResponse] = []
    for match in combined:
        entity_type = match["entity_type"]
        value = match["value"]
        normalized_value = normalize(entity_type, value)

        entities.append(
            ExtractedEntityResponse(
                entity_id=str(uuid.uuid4()),
                entity_type=entity_type,
                value=value,
                normalized_value=normalized_value,
                confidence=match["confidence"],
                start_offset=match["start_offset"],
                end_offset=match["end_offset"],
                source_field=source_field,
                case_id=case_id,
            )
        )

    return entities
