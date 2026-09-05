from datetime import UTC, datetime

from app.schemas.entity import EntityResponse, EntityType
from app.services.privacy import masked_entity, redact_victim_text


def _victim_entity() -> EntityResponse:
    now = datetime.now(UTC)
    return EntityResponse(
        id="ent-victim",
        case_id="case-private",
        name="Kavita Rao",
        entity_type=EntityType.PERSON,
        description="Complainant",
        properties={
            "privacy_classification": "VICTIM_PII",
            "occurrences": [{
                "value": "Kavita Rao",
                "normalized_value": "kavita rao",
                "document_id": "doc-1",
                "start_offset": 12,
                "end_offset": 22,
            }],
        },
        confidence_score=0.97,
        created_at=now,
        updated_at=now,
    )


def test_masked_entity_preserves_provenance_but_removes_victim_values():
    masked = masked_entity(_victim_entity())

    assert masked.is_masked is True
    assert masked.name == "[VICTIM DATA MASKED]"
    occurrence = masked.properties["occurrences"][0]
    assert occurrence["value"] == "[VICTIM DATA MASKED]"
    assert occurrence["normalized_value"] == "[VICTIM DATA MASKED]"
    assert occurrence["document_id"] == "doc-1"
    assert occurrence["start_offset"] == 12
    assert occurrence["end_offset"] == 22


def test_report_narrative_redaction_is_case_insensitive():
    narrative = "Complainant KAVITA RAO reported fraud. Kavita Rao supplied evidence."

    redacted = redact_victim_text(narrative, [_victim_entity()])

    assert "kavita rao" not in redacted.casefold()
    assert redacted.count("[VICTIM DATA MASKED]") == 2
