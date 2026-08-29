"""
CrimeLensAI — NLP Extraction Pipeline
========================================
Combines spaCy NER (PERSON, ORG, LOCATION) with regex extractors
(PHONE, VEHICLE, UPI_ID) and deduplicates overlapping spans.

All offsets are character positions in the **original** input text.
"""

from __future__ import annotations

import re
from typing import List, Tuple

import spacy

from app.models.schemas import EntityType, ExtractedEntity

# ── Load spaCy model (once at import time) ──────────────────

_nlp = spacy.load("en_core_web_sm")

# ── spaCy label → our EntityType ────────────────────────────

_SPACY_MAP: dict[str, EntityType] = {
    "PERSON": EntityType.PERSON,
    "ORG":    EntityType.ORG,
    "GPE":    EntityType.LOCATION,
    "LOC":    EntityType.LOCATION,
    "FAC":    EntityType.LOCATION,
}

# ── Confidence values (deterministic) ───────────────────────

_SPACY_CONFIDENCE: dict[str, float] = {
    "PERSON": 0.85,
    "ORG":    0.80,
    "GPE":    0.78,
    "LOC":    0.75,
    "FAC":    0.72,
}

# ── Regex patterns ──────────────────────────────────────────

# Indian phone numbers — ordered from most-specific to least
_PHONE_PATTERNS: list[tuple[re.Pattern, float]] = [
    # +91 prefix (with optional separator)
    (re.compile(r"\+91[\s\-]?[6-9]\d{9}"), 0.95),
    # 0-prefix landline / mobile
    (re.compile(r"\b0[6-9]\d{9}\b"), 0.90),
    # Plain 10-digit mobile
    (re.compile(r"(?<!\d)[6-9]\d{9}(?!\d)"), 0.85),
]

# Indian vehicle registration: SS DD LLL NNNN (with optional separators)
_VEHICLE_RE = re.compile(
    r"\b([A-Z]{2})[\s\-]?(\d{1,2})[\s\-]?([A-Z]{1,3})[\s\-]?(\d{4})\b",
    re.IGNORECASE,
)

# UPI ID: username@handle
_UPI_RE = re.compile(
    r"\b[a-zA-Z0-9._\-]+@"
    r"(?:upi|paytm|ybl|oksbi|okicici|okaxis|okhdfcbank|apl|ibl|axl|"
    r"sbi|icici|hdfc|axisbank|kotak|indus|federal|rbl|citi|idbi|"
    r"pnb|boi|bob|iob|canara|syndicate|allahabad|vijaya|dena|"
    r"corp|andhra|uco|oriental)\b",
    re.IGNORECASE,
)


# ── Internal helpers ────────────────────────────────────────

def _spans_overlap(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    """True when two char-spans overlap ≥ 50 % of the shorter span."""
    overlap = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    shorter = min(a[1] - a[0], b[1] - b[0])
    return shorter > 0 and (overlap / shorter) >= 0.5


def _extract_spacy(text: str, source_field: str) -> List[ExtractedEntity]:
    doc = _nlp(text)
    out: list[ExtractedEntity] = []
    for ent in doc.ents:
        etype = _SPACY_MAP.get(ent.label_)
        if etype is None:
            continue
        conf = _SPACY_CONFIDENCE.get(ent.label_, 0.70)
        out.append(ExtractedEntity(
            entity_type=etype,
            value=ent.text,
            confidence=conf,
            start_offset=ent.start_char,
            end_offset=ent.end_char,
            source_field=source_field,
        ))
    return out


def _extract_phones(text: str, source_field: str) -> List[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    seen: list[Tuple[int, int]] = []
    for pattern, conf in _PHONE_PATTERNS:
        for m in pattern.finditer(text):
            span = (m.start(), m.end())
            if any(_spans_overlap(span, s) for s in seen):
                continue
            seen.append(span)
            out.append(ExtractedEntity(
                entity_type=EntityType.PHONE,
                value=m.group(),
                confidence=conf,
                start_offset=m.start(),
                end_offset=m.end(),
                source_field=source_field,
            ))
    return out


def _extract_vehicles(text: str, source_field: str) -> List[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for m in _VEHICLE_RE.finditer(text):
        out.append(ExtractedEntity(
            entity_type=EntityType.VEHICLE,
            value=m.group(),
            confidence=0.95,
            start_offset=m.start(),
            end_offset=m.end(),
            source_field=source_field,
        ))
    return out


def _extract_upi(text: str, source_field: str) -> List[ExtractedEntity]:
    out: list[ExtractedEntity] = []
    for m in _UPI_RE.finditer(text):
        out.append(ExtractedEntity(
            entity_type=EntityType.UPI_ID,
            value=m.group(),
            confidence=0.95,
            start_offset=m.start(),
            end_offset=m.end(),
            source_field=source_field,
        ))
    return out


def _deduplicate(entities: List[ExtractedEntity]) -> List[ExtractedEntity]:
    """Remove overlapping entities, keeping the higher-confidence one.

    When confidence is equal, regex-derived types (PHONE, VEHICLE, UPI_ID)
    are preferred over spaCy-derived types because they are more specific.
    """
    _REGEX_TYPES = {EntityType.PHONE, EntityType.VEHICLE, EntityType.UPI_ID}

    # Sort: earliest first, then highest confidence, then regex-preferred
    ranked = sorted(
        entities,
        key=lambda e: (
            e.start_offset,
            -e.confidence,
            0 if e.entity_type in _REGEX_TYPES else 1,
        ),
    )

    accepted: list[ExtractedEntity] = []
    for ent in ranked:
        span = (ent.start_offset, ent.end_offset)
        overlap_idx: int | None = None
        for i, a in enumerate(accepted):
            if _spans_overlap(span, (a.start_offset, a.end_offset)):
                overlap_idx = i
                break
        if overlap_idx is not None:
            existing = accepted[overlap_idx]
            # Replace only if strictly better
            if ent.confidence > existing.confidence:
                accepted[overlap_idx] = ent
            elif (
                ent.confidence == existing.confidence
                and ent.entity_type in _REGEX_TYPES
                and existing.entity_type not in _REGEX_TYPES
            ):
                accepted[overlap_idx] = ent
            # else keep existing
        else:
            accepted.append(ent)

    return sorted(accepted, key=lambda e: e.start_offset)


# ── Public API ──────────────────────────────────────────────

def extract_entities(
    text: str,
    source_type: str = "fir_text",
) -> List[ExtractedEntity]:
    """Run the full extraction pipeline on *text*.

    Returns a deduplicated list of ``ExtractedEntity`` sorted by
    ``start_offset``.
    """
    if not text or not text.strip():
        return []

    source_field = "text"  # the request field name the text came from

    all_ents: list[ExtractedEntity] = []
    all_ents.extend(_extract_spacy(text, source_field))
    all_ents.extend(_extract_phones(text, source_field))
    all_ents.extend(_extract_vehicles(text, source_field))
    all_ents.extend(_extract_upi(text, source_field))

    return _deduplicate(all_ents)
