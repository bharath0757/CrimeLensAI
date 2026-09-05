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

from app.extractors.normalizers import normalize
from app.extractors.regex_extractors import RawMatch, run_all_regex
from app.extractors.spacy_extractors import extract_spacy_entities
from app.models.schemas import ExtractedEntityResponse


def _spans_overlap(a_start: int, a_end: int, b_start: int, b_end: int) -> bool:
    """Return True if two character spans overlap."""
    return a_start < b_end and b_start < a_end


def _is_identifier_heading(match: RawMatch, text: str, identifiers: list[RawMatch]) -> bool:
    """A label directly preceding a parsed identifier is not a named entity.

    Context matters: a standalone name such as Pan is not globally blacklisted.
    """
    headings = {
        "UPI": "UPI_ID", "PAN": "PAN", "AADHAAR": "AADHAAR",
        "PASSPORT": "PASSPORT", "PHONE": "PHONE", "EMAIL": "EMAIL",
    }
    kind = headings.get(match["value"].strip().upper())
    if not kind or match["entity_type"] not in {"PERSON", "ORG", "LOCATION"}:
        return False
    for identifier in identifiers:
        gap = identifier["start_offset"] - match["end_offset"]
        if identifier["entity_type"] == kind and 0 <= gap <= 12:
            between = text[match["end_offset"]:identifier["start_offset"]].strip(" :#.-").casefold()
            if between in {"", "id", "no", "number"}:
                return True
    return False


def _deduplicate(
    regex_matches: list[RawMatch],
    spacy_matches: list[RawMatch],
) -> list[RawMatch]:
    """Merge regex and spaCy matches, preferring regex on overlap.

    For each spaCy match, if it overlaps with any regex match we
    discard the spaCy match.  This prevents double-counting phone
    numbers that spaCy might tag as CARDINAL, etc.
    """
    priority = {
        "AADHAAR": 100,
        "PAN": 100,
        "PASSPORT": 100,
        "BANK_ACCOUNT": 100,
        "EMAIL": 100,
        "UPI_ID": 100,
        "PHONE": 95,
        "VEHICLE": 95,
        "IPC_SECTION": 95,
        "DATE": 90,
        "PERSON": 60,
        "ORG": 60,
        "LOCATION": 50,
    }
    combined: list[RawMatch] = []
    for candidate in sorted(
        regex_matches,
        key=lambda item: (
            -priority.get(item["entity_type"], 0),
            -(item["end_offset"] - item["start_offset"]),
            item["start_offset"],
        ),
    ):
        duplicate = any(
            candidate["entity_type"] == existing["entity_type"]
            and candidate["start_offset"] == existing["start_offset"]
            and candidate["end_offset"] == existing["end_offset"]
            for existing in combined
        )
        conflicting_overlap = any(
            _spans_overlap(
                candidate["start_offset"],
                candidate["end_offset"],
                existing["start_offset"],
                existing["end_offset"],
            )
            for existing in combined
        )
        if not duplicate and not conflicting_overlap:
            combined.append(candidate)

    for sm in spacy_matches:
        overlaps = any(
            _spans_overlap(sm["start_offset"], sm["end_offset"],
                           rm["start_offset"], rm["end_offset"])
            for rm in combined
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
    spacy_matches = [match for match in spacy_matches if not _is_identifier_heading(match, text, regex_matches)]
    combined = _deduplicate(regex_matches, spacy_matches)

    entities: list[ExtractedEntityResponse] = []
    for match in sorted(combined, key=lambda item: item["start_offset"]):
        entity_type = match["entity_type"]
        value = match["value"]
        normalized_value = normalize(entity_type, value)

        entities.append(
            ExtractedEntityResponse(
                entity_id=str(
                    uuid.uuid5(
                        uuid.NAMESPACE_URL,
                        f"crimelens:{case_id or 'unassigned'}:{source_field}:"
                        f"{entity_type}:{normalized_value}:{match['start_offset']}:{match['end_offset']}",
                    )
                ),
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
