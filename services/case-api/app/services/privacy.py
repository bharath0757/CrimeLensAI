"""Default-deny presentation rules for victim-identifying entity fields."""

from __future__ import annotations

import re
from typing import Any

from app.schemas.entity import EntityResponse


def is_victim_pii(entity: EntityResponse) -> bool:
    properties = entity.properties or {}
    classification = str(properties.get("privacy_classification", "")).upper()
    subject_role = str(properties.get("subject_role", "")).upper()
    return (
        properties.get("is_victim") is True
        or classification in {"VICTIM_PII", "RESTRICTED_VICTIM"}
        or subject_role in {"VICTIM", "COMPLAINANT"}
    )


def _redact_properties(value: Any) -> Any:
    if isinstance(value, list):
        return [_redact_properties(item) for item in value]
    if not isinstance(value, dict):
        return value
    result = {}
    for key, item in value.items():
        if key.casefold() in {"value", "normalized_value", "name", "address", "email", "phone"}:
            result[key] = "[VICTIM DATA MASKED]"
        else:
            result[key] = _redact_properties(item)
    return result


def masked_entity(entity: EntityResponse) -> EntityResponse:
    if not is_victim_pii(entity):
        return entity
    return entity.model_copy(update={
        "name": "[VICTIM DATA MASKED]",
        "description": "Victim-identifying data is protected. Use the audited unmask action when operationally necessary.",
        "properties": _redact_properties(entity.properties),
        "is_masked": True,
    })


def redact_victim_text(text: str, entities: list[EntityResponse]) -> str:
    """Remove victim identifiers from narrative text using reviewed extraction values."""
    protected_values: set[str] = set()
    for entity in entities:
        if not is_victim_pii(entity):
            continue
        if entity.name.strip():
            protected_values.add(entity.name.strip())
        properties = entity.properties or {}
        occurrences = properties.get("occurrences", [])
        if isinstance(occurrences, list):
            for occurrence in occurrences:
                if not isinstance(occurrence, dict):
                    continue
                for key in ("value", "normalized_value", "name"):
                    candidate = occurrence.get(key)
                    if isinstance(candidate, str) and candidate.strip():
                        protected_values.add(candidate.strip())

    redacted = text
    for value in sorted(protected_values, key=len, reverse=True):
        redacted = re.sub(re.escape(value), "[VICTIM DATA MASKED]", redacted, flags=re.IGNORECASE)
    return redacted
