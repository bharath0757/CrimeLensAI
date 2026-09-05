"""CrimeLensAI Graph Service — entity/relationship business logic."""

import re

from app.models import EntityInput, RelationshipInput
from app.models.schemas import (
    EntityUpsertRequest,
    EntityUpsertResponse,
    LinkageResponse,
    LinkedCase,
    RelationshipCreateRequest,
    RelationshipCreateResponse,
    SharedEntity,
)
from app.store import InMemoryGraphStore

ENTITY_WEIGHTS = {
    "PHONE": 1.0, "UPI_ID": 1.0, "VEHICLE": 0.95,
    "PERSON": 0.65, "ORG": 0.45, "LOCATION": 0.25,
}


def canonicalize(entity_type: str, value: str) -> str:
    """Normalize entity value for deduplication."""
    if entity_type == "PHONE":
        return re.sub(r"\D", "", value)[-10:]
    if entity_type == "VEHICLE":
        return re.sub(r"[^A-Z0-9]", "", value.upper())
    if entity_type == "UPI_ID":
        return value.strip().lower()
    return re.sub(r"\s+", " ", value).strip().casefold()


class GraphService:
    """Wraps the InMemoryGraphStore with typed request/response models."""

    def __init__(self, store: InMemoryGraphStore) -> None:
        self._store = store

    def _entity_input_from_request(self, request: EntityUpsertRequest) -> EntityInput:
        canonical_value = request.normalized_value or canonicalize(
            request.entity_type.value, request.value,
        )
        return EntityInput(
            id=request.entity_id,
            entity_type=request.entity_type,
            value=request.value,
            canonical_value=canonical_value,
            confidence=request.confidence,
            case_id=request.case_id,
            source_field=request.source_field,
            start_offset=request.start_offset,
            end_offset=request.end_offset,
        )

    def upsert_entity(self, request: EntityUpsertRequest) -> EntityUpsertResponse:
        """Upsert an entity node and link it to its case."""
        # Check if canonical already exists (to determine created vs exists)
        entity_input = self._entity_input_from_request(request)
        canonical = canonicalize(request.entity_type.value, entity_input.canonical_value or request.value)
        key = (request.entity_type.value, canonical)
        already_existed = key in self._store.canonical_index

        result = self._store.upsert_entity(entity_input)

        # result is {"entity": {...}, "alerts": [...]}
        entity = result["entity"]
        entity_id = entity["id"]

        # Gather all case IDs linked to this entity
        case_ids = sorted(
            case for case, ids in self._store.case_entities.items()
            if entity_id in ids
        )

        created = not already_existed
        canonical_value = entity.get("canonical_value", canonical)
        entity_type = entity.get("entity_type", request.entity_type.value)

        action = "created and linked to" if created else "already exists, linked to"
        explanation = (
            f"Entity {entity_type} '{entity['value']}' {action} "
            f"{', '.join(case_ids)}."
        )

        return EntityUpsertResponse(
            status="created" if created else "exists",
            entity_id=entity_id,
            entity_type=entity_type,
            canonical_value=canonical_value,
            created=created,
            case_ids=case_ids,
            explanation=explanation,
        )

    def create_relationship(self, request: RelationshipCreateRequest) -> RelationshipCreateResponse:
        """Create a relationship between two entities with evidence metadata."""
        rel_input = RelationshipInput(
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            relationship_type=request.relationship_type,
            source_case_id=request.source_case_id,
            confidence=request.confidence,
            why_linked=request.why_linked,
            evidence_record_id=request.evidence_record_id,
            evidence=request.evidence,
        )
        rel = self._store.create_relationship(rel_input)
        rel_id = rel["id"]

        return RelationshipCreateResponse(
            status="created",
            relationship_id=rel_id,
            source_entity_id=request.source_entity_id,
            target_entity_id=request.target_entity_id,
            relationship_type=request.relationship_type,
            explanation=request.why_linked,
        )

    def get_linkage(self, case_id: str) -> LinkageResponse:
        """Find cross-case linkage through shared entities."""
        store_result = self._store.get_linkage(case_id)
        linked_cases: list[LinkedCase] = []

        for lc in store_result.get("linked_cases", []):
            shared_ents = []
            for e in lc.get("shared_entities", []):
                shared_ents.append(SharedEntity(
                    entity_id=e.get("id", e.get("entity_id", "")),
                    entity_type=e["entity_type"],
                    value=e["value"],
                    canonical_value=e.get("canonical_value", ""),
                    confidence=e.get("confidence", 1.0),
                ))

            # Use the store's computed link_strength and explanation if available
            link_strength = lc.get("link_strength", 0.0)
            explanation = lc.get("explanation", "")

            if not explanation:
                signals = ", ".join(
                    f"{se.entity_type} {se.value}" for se in shared_ents
                )
                explanation = (
                    f"{case_id} and {lc['case_id']} are linked because "
                    f"both reference {signals}."
                )

            linked_cases.append(LinkedCase(
                case_id=lc["case_id"],
                shared_entities=shared_ents,
                link_strength=link_strength,
                explanation=explanation,
            ))

        return LinkageResponse(case_id=case_id, linked_cases=linked_cases)
