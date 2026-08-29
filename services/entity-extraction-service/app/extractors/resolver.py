"""
CrimeLensAI — Lightweight Entity Resolution
==============================================
Groups duplicate / variant entities using rapidfuzz.

Strategy per entity type
------------------------
* PERSON, ORG, LOCATION — fuzzy string matching with initial-expansion
  heuristics so that "R. Kumar" merges with "Rajesh Kumar".
* PHONE, VEHICLE, UPI_ID — exact matching after normalisation (strip
  separators, keep last 10 digits for phones, etc.).

No database lookups; purely in-memory and deterministic.
"""

from __future__ import annotations

import re
from typing import List

from rapidfuzz import fuzz

from app.models.schemas import EntityResolutionGroup, EntityType, ExtractedEntity

# Types where we apply fuzzy matching
_FUZZY_TYPES = {EntityType.PERSON, EntityType.ORG, EntityType.LOCATION}

# Minimum score (0–100) to consider two values the same entity
_FUZZY_THRESHOLD = 85


# ── Normalisation helpers ───────────────────────────────────

def _norm_text(value: str) -> str:
    """Lower-case, collapse whitespace."""
    return " ".join(value.strip().lower().split())


def _norm_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    return digits[-10:] if len(digits) >= 10 else digits


def _norm_vehicle(value: str) -> str:
    return re.sub(r"[\s\-]", "", value).upper()


def _norm_upi(value: str) -> str:
    return value.strip().lower()


def _norm_structured(value: str, etype: EntityType) -> str:
    if etype == EntityType.PHONE:
        return _norm_phone(value)
    if etype == EntityType.VEHICLE:
        return _norm_vehicle(value)
    if etype == EntityType.UPI_ID:
        return _norm_upi(value)
    return value.strip()


# ── Initial-aware name similarity ───────────────────────────

def _tokenize(name: str) -> list[str]:
    """Split a name into lower-cased tokens, stripping periods."""
    return [t for t in name.replace(".", " ").lower().split() if t]


def _initials_match(tokens_a: list[str], tokens_b: list[str]) -> bool:
    """Check whether one name is an abbreviated form of the other.

    Returns True when every token in the shorter list either
    (a) equals a token in the longer list, or
    (b) is a single character that matches the first letter of a token
        in the longer list.
    """
    shorter, longer = (
        (tokens_a, tokens_b) if len(tokens_a) <= len(tokens_b)
        else (tokens_b, tokens_a)
    )
    if not shorter or not longer:
        return False

    used = [False] * len(longer)
    for s_tok in shorter:
        found = False
        for i, l_tok in enumerate(longer):
            if used[i]:
                continue
            if s_tok == l_tok:
                used[i] = True
                found = True
                break
            if len(s_tok) == 1 and l_tok.startswith(s_tok):
                used[i] = True
                found = True
                break
        if not found:
            return False
    return True


def _name_similarity(a: str, b: str) -> float:
    """Score (0–100) for two entity names, handling initials."""
    na, nb = _norm_text(a), _norm_text(b)

    # Standard fuzzy scores
    score = max(
        fuzz.ratio(na, nb),
        fuzz.token_sort_ratio(na, nb),
        fuzz.partial_ratio(na, nb),
    )

    # Boost for initial-match (e.g. "R. Kumar" ~ "Rajesh Kumar")
    if _initials_match(_tokenize(a), _tokenize(b)):
        score = max(score, 90)

    return score


# ── Grouping logic ──────────────────────────────────────────

def _fuzzy_group(
    entities: List[ExtractedEntity],
    entity_type: EntityType,
) -> List[EntityResolutionGroup]:
    """Cluster entities by fuzzy string similarity."""
    clusters: list[list[ExtractedEntity]] = []

    for ent in entities:
        merged = False
        for cluster in clusters:
            canonical = max(cluster, key=lambda e: len(e.value))
            if _name_similarity(ent.value, canonical.value) >= _FUZZY_THRESHOLD:
                cluster.append(ent)
                merged = True
                break
        if not merged:
            clusters.append([ent])

    groups: list[EntityResolutionGroup] = []
    for cluster in clusters:
        canonical = max(cluster, key=lambda e: len(e.value))
        # compute average pairwise merge confidence
        if len(cluster) <= 1:
            merge_conf = 1.0
        else:
            scores = [
                _name_similarity(e.value, canonical.value) / 100.0
                for e in cluster
                if e is not canonical
            ]
            merge_conf = sum(scores) / len(scores) if scores else 1.0

        groups.append(EntityResolutionGroup(
            canonical_value=canonical.value,
            entity_type=entity_type,
            variants=cluster,
            merge_confidence=round(min(merge_conf, 1.0), 2),
        ))
    return groups


def _exact_group(
    entities: List[ExtractedEntity],
    entity_type: EntityType,
) -> List[EntityResolutionGroup]:
    """Cluster structured entities by normalised exact match."""
    buckets: dict[str, list[ExtractedEntity]] = {}
    for ent in entities:
        key = _norm_structured(ent.value, entity_type)
        buckets.setdefault(key, []).append(ent)

    groups: list[EntityResolutionGroup] = []
    for _key, cluster in buckets.items():
        canonical = max(cluster, key=lambda e: len(e.value))
        groups.append(EntityResolutionGroup(
            canonical_value=canonical.value,
            entity_type=entity_type,
            variants=cluster,
            merge_confidence=1.0,
        ))
    return groups


# ── Public API ──────────────────────────────────────────────

def resolve_entities(
    entities: List[ExtractedEntity],
) -> List[EntityResolutionGroup]:
    """Group duplicate / variant entities.

    Returns a list of ``EntityResolutionGroup`` objects, each containing
    the canonical value, entity type, full variant entities, and a
    merge-confidence score.
    """
    if not entities:
        return []

    by_type: dict[EntityType, list[ExtractedEntity]] = {}
    for ent in entities:
        by_type.setdefault(ent.entity_type, []).append(ent)

    groups: list[EntityResolutionGroup] = []
    for etype, ents in by_type.items():
        if etype in _FUZZY_TYPES:
            groups.extend(_fuzzy_group(ents, etype))
        else:
            groups.extend(_exact_group(ents, etype))

    return groups
