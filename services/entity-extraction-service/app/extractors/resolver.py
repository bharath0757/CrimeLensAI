"""
CrimeLensAI — Entity Resolution
==================================
Groups extracted entities that likely refer to the same real-world
identity.

Type partitions:
  * **Exact-match types** (PHONE, VEHICLE, UPI_ID): entities are
    grouped when their ``normalized_value`` matches exactly.
    Resolution method: ``"exact_match"``, confidence: 1.0.

  * **Fuzzy identity types** (PERSON, ORG, LOCATION): entities are
    grouped using ``rapidfuzz.fuzz.token_sort_ratio`` when the
    score exceeds ``RESOLUTION_FUZZY_THRESHOLD`` (default 80).
    Resolution method: ``"fuzzy_match"``, confidence = score / 100.

  * **Non-resolvable / context types** (DATE): passed through
    without identity resolution.  Dates are contextual metadata,
    not real-world identities.

Canonical entity IDs are **deterministic** — derived from a
SHA-256 hash of ``entity_type:normalized_value`` so that the same
identity always produces the same ID across requests.

The resolver is **conservative** — it does NOT merge entities
across different ``entity_type``s and uses a high threshold to
avoid false merges.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict

from rapidfuzz import fuzz

from app.core.config import settings
from app.extractors.normalizers import normalize
from app.models.schemas import ExtractedEntityResponse, ResolvedGroup

# Types where normalized_value equality is sufficient for grouping
_EXACT_TYPES = {"PHONE", "VEHICLE", "UPI_ID", "AADHAAR", "PAN", "PASSPORT", "BANK_ACCOUNT", "EMAIL"}

# Types excluded from identity resolution (contextual, not identities)
_SKIP_TYPES = {"DATE", "IPC_SECTION"}


def _make_canonical_id(entity_type: str, normalized_value: str) -> str:
    """Generate a deterministic canonical entity ID.

    Uses SHA-256 of ``entity_type:normalized_value`` so that the
    same identity always produces the same ID, and different entity
    types never collide.
    """
    key = f"{entity_type}:{normalized_value}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _pick_canonical(mentions: list[ExtractedEntityResponse]) -> str:
    """Pick the best canonical value from a group of mentions.

    Strategy: pick the longest original value (most complete form),
    breaking ties by alphabetical order for determinism.
    """
    return max(mentions, key=lambda m: (len(m.value), m.value)).value


def _resolve_exact(
    entities: list[ExtractedEntityResponse],
) -> list[ResolvedGroup]:
    """Group entities by exact ``normalized_value`` match."""
    buckets: dict[str, list[ExtractedEntityResponse]] = defaultdict(list)
    for ent in entities:
        buckets[ent.normalized_value].append(ent)

    groups: list[ResolvedGroup] = []
    for _norm_val, mentions in buckets.items():
        groups.append(
            ResolvedGroup(
                canonical_entity_id=_make_canonical_id(
                    mentions[0].entity_type, _norm_val,
                ),
                canonical_value=_pick_canonical(mentions),
                entity_type=mentions[0].entity_type,
                variants=mentions,
                merge_confidence=1.0,
                resolution_method="exact_match",
            )
        )
    return groups


def _resolve_fuzzy(
    entities: list[ExtractedEntityResponse],
    threshold: float,
) -> list[ResolvedGroup]:
    """Group entities by fuzzy string similarity on ``normalized_value``.

    Uses union-find style clustering: for each pair above threshold,
    merge their groups.
    """
    n = len(entities)
    # parent[i] = index of parent in union-find
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i: int, j: int) -> None:
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[ri] = rj

    # Compare all pairs (O(n²) — acceptable for prototype entity counts)
    for i in range(n):
        for j in range(i + 1, n):
            score = fuzz.token_sort_ratio(
                entities[i].normalized_value,
                entities[j].normalized_value,
            )
            if score >= threshold:
                union(i, j)

    # Collect groups
    clusters: dict[int, list[int]] = defaultdict(list)
    for i in range(n):
        clusters[find(i)].append(i)

    groups: list[ResolvedGroup] = []
    for indices in clusters.values():
        mentions = [entities[i] for i in indices]
        # Average pairwise score as merge confidence
        if len(mentions) == 1:
            conf = 1.0
        else:
            scores: list[float] = []
            for a in range(len(indices)):
                for b in range(a + 1, len(indices)):
                    scores.append(
                        fuzz.token_sort_ratio(
                            entities[indices[a]].normalized_value,
                            entities[indices[b]].normalized_value,
                        )
                        / 100.0
                    )
            conf = sum(scores) / len(scores) if scores else 1.0

        canonical = _pick_canonical(mentions)
        # Use the normalized value of the canonical representative
        # to ensure deterministic IDs
        canonical_norm = normalize(mentions[0].entity_type, canonical)

        groups.append(
            ResolvedGroup(
                canonical_entity_id=_make_canonical_id(
                    mentions[0].entity_type, canonical_norm,
                ),
                canonical_value=canonical,
                entity_type=mentions[0].entity_type,
                variants=mentions,
                merge_confidence=round(conf, 4),
                resolution_method="fuzzy_match",
            )
        )
    return groups


def resolve_entities(
    entities: list[ExtractedEntityResponse],
) -> list[ResolvedGroup]:
    """Resolve a list of extracted entities into canonical groups.

    Parameters
    ----------
    entities:
        Flat list of extracted entities (may span multiple cases).

    Returns
    -------
    list[ResolvedGroup]
        Resolved groups ready for consumption by the graph service.
    """
    # Partition by entity_type
    by_type: dict[str, list[ExtractedEntityResponse]] = defaultdict(list)
    for ent in entities:
        by_type[ent.entity_type].append(ent)

    all_groups: list[ResolvedGroup] = []
    threshold = settings.RESOLUTION_FUZZY_THRESHOLD

    for etype, ents in by_type.items():
        if etype in _SKIP_TYPES:
            # DATE and other context types are not identities — skip
            continue
        if etype in _EXACT_TYPES:
            all_groups.extend(_resolve_exact(ents))
        else:
            all_groups.extend(_resolve_fuzzy(ents, threshold))

    return all_groups
