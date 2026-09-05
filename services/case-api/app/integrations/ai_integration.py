"""Real, awaited FIR extraction with reviewable provenance and graph writes."""

from __future__ import annotations

import asyncio
import logging
import re
from abc import ABC, abstractmethod

import httpx
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.entity_identity import normalized_entity_value
from app.integrations.graph_integration import graph_service_integration
from app.repositories.registry import (
    case_repository,
    document_repository,
    entity_repository,
)
from app.schemas.document import DocumentProcessingStatusResponse, ProcessingStatus
from app.schemas.entity import EntityCreate, EntityType, EntityUpdate
from app.services.document_text import DocumentTextError, read_document

logger = logging.getLogger(__name__)
_TYPE_MAP = {"PHONE": "PHONE_NUMBER", "ORG": "ORGANIZATION"}
_VICTIM_CONTEXT = re.compile(
    r"\b(?:victim|complainant)(?:'s)?(?:\s+(?:name|phone|mobile|email|aadhaar|pan|passport|account|upi))?\s*[:=-]?\s*$",
    re.IGNORECASE,
)


class ExtractionMention(BaseModel):
    entity_id: str
    entity_type: str
    value: str = Field(min_length=1, max_length=200)
    normalized_value: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    start_offset: int = Field(ge=0)
    end_offset: int = Field(ge=0)
    source_field: str
    case_id: str | None = None


class ExtractionResult(BaseModel):
    entities: list[ExtractionMention]
    model: str
    warnings: list[str] = Field(default_factory=list)


class AIServiceInterface(ABC):
    @abstractmethod
    async def extract_text(self, text: str, case_id: str | None = None) -> ExtractionResult: ...

    @abstractmethod
    async def process_document(self, document_id: str, case_id: str, file_path: str) -> bool: ...

    @abstractmethod
    async def get_processing_status(self, document_id: str) -> DocumentProcessingStatusResponse: ...


class IntegratedAIService(AIServiceInterface):
    def __init__(
        self, doc_repo=document_repository, ent_repo=entity_repository,
        c_repo=case_repository, graph_service=graph_service_integration,
        base_url: str | None = None, transport: httpx.AsyncBaseTransport | None = None,
    ):
        self._doc_repo = doc_repo
        self._ent_repo = ent_repo
        self._case_repo = c_repo
        self._graph = graph_service
        self._base_url = (base_url or settings.AI_SERVICE_URL).rstrip("/")
        self._transport = transport

    async def extract_text(self, text: str, case_id: str | None = None) -> ExtractionResult:
        async with httpx.AsyncClient(timeout=90.0, transport=self._transport) as client:
            response = await client.post(
                f"{self._base_url}/api/v1/extract",
                json={"text": text, "case_id": case_id, "source_field": "document_text"},
                headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN},
            )
            response.raise_for_status()
            result = ExtractionResult.model_validate(response.json())
        # Validate the complete response before storing any entity.
        for mention in result.entities:
            EntityType(_TYPE_MAP.get(mention.entity_type, mention.entity_type))
            if mention.case_id != case_id or not (
                mention.start_offset < mention.end_offset <= len(text)
                and text[mention.start_offset:mention.end_offset] == mention.value
            ):
                raise ValueError("Extraction service returned invalid source provenance")
        return result

    async def process_document(self, document_id: str, case_id: str, file_path: str) -> bool:
        document = await self._doc_repo.get_by_id(document_id)
        if not document or document.case_id != case_id or document.file_path != file_path:
            return False
        if document.processing_status == ProcessingStatus.COMPLETED:
            return True
        if document.processing_status == ProcessingStatus.PROCESSING:
            return False
        await self._doc_repo.update_status(document_id, ProcessingStatus.PROCESSING)
        try:
            source = await asyncio.to_thread(read_document, file_path)
            result = await self.extract_text(source.text, case_id)
            grouped: dict[tuple[EntityType, str], list[ExtractionMention]] = {}
            for mention in result.entities:
                kind = EntityType(_TYPE_MAP.get(mention.entity_type, mention.entity_type))
                grouped.setdefault((kind, normalized_entity_value(kind, mention.normalized_value)), []).append(mention)
            # Load every entity, not just the first UI-sized page.
            existing = {}
            skip = 0
            while True:
                page, total = await self._ent_repo.list_by_case(case_id, skip=skip, limit=500)
                for entity in page:
                    key = (entity.entity_type, normalized_entity_value(entity.entity_type, entity.name))
                    existing[key] = entity
                skip += len(page)
                if skip >= total or not page:
                    break
            for key, mentions in grouped.items():
                kind, normalized = key
                current = existing.get(key)
                occurrences = list(current.properties.get("occurrences", [])) if current else []
                for mention in mentions:
                    occurrence = {
                        "document_id": document_id, "document_sha256": source.sha256,
                        "start_offset": mention.start_offset, "end_offset": mention.end_offset,
                        "source_field": "document_text", "value": mention.value,
                    }
                    if occurrence not in occurrences:
                        occurrences.append(occurrence)
                properties = {
                    **(current.properties if current else {}),
                    "normalized_value": normalized, "occurrences": occurrences,
                    "extraction_model": result.model, "extraction_warnings": result.warnings,
                }
                if any(_is_victim_mention(source.text, mention) for mention in mentions):
                    properties.update(
                        privacy_classification="VICTIM_PII",
                        subject_role="VICTIM",
                    )
                confidence = max(m.confidence for m in mentions)
                if current:
                    entity = await self._ent_repo.update(current.id, EntityUpdate(
                        properties=properties,
                        confidence_score=max(current.confidence_score, confidence),
                    ))
                else:
                    entity = await self._ent_repo.create(case_id, EntityCreate(
                        name=mentions[0].value, entity_type=kind, properties=properties,
                        confidence_score=confidence, source_document_id=document_id,
                    ))
                    await self._case_repo.update_counts(case_id, entity_delta=1)
                await self._graph.sync_entity(case_id, entity)
            # Co-occurrence is not evidence of ownership or a criminal relationship.
            # Structured CDR/transactions and reviewed assertions create those edges.
            await self._doc_repo.update_extraction_counts(
                document_id, len(grouped) - document.extracted_entity_count,
                -document.extracted_relationship_count,
            )
            await self._doc_repo.update_status(document_id, ProcessingStatus.COMPLETED)
            return True
        except Exception as exc:
            logger.error("Document processing failed: document=%s error_type=%s", document_id, type(exc).__name__)
            message = str(exc) if isinstance(exc, DocumentTextError) else "Extraction or graph persistence failed. Retry after checking service health."
            await self._doc_repo.update_status(document_id, ProcessingStatus.FAILED, error_message=message)
            if isinstance(exc, DocumentTextError):
                raise
            return False

    async def get_processing_status(self, document_id: str) -> DocumentProcessingStatusResponse:
        document = await self._doc_repo.get_by_id(document_id)
        if not document:
            return DocumentProcessingStatusResponse(
                document_id=document_id, case_id="", processing_status=ProcessingStatus.FAILED,
                message="Document not found",
            )
        return DocumentProcessingStatusResponse(
            document_id=document.id, case_id=document.case_id,
            processing_status=document.processing_status,
            progress_percentage=100.0 if document.processing_status == ProcessingStatus.COMPLETED else 0.0,
            extracted_entity_count=document.extracted_entity_count,
            extracted_relationship_count=document.extracted_relationship_count,
            message=document.error_message or document.processing_status.value,
        )


ai_service_integration = IntegratedAIService()


def _is_victim_mention(text: str, mention: ExtractionMention) -> bool:
    prefix = text[max(0, mention.start_offset - 70):mention.start_offset]
    return bool(_VICTIM_CONTEXT.search(prefix))
