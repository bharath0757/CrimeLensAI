import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from app.schemas.document import ProcessingStatus, DocumentProcessingStatusResponse
from app.repositories.document_repo import document_repository, DocumentRepositoryInterface
from app.repositories.entity_repo import entity_repository, EntityRepositoryInterface
from app.repositories.relationship_repo import relationship_repository, RelationshipRepositoryInterface
from app.repositories.case_repo import case_repository, CaseRepositoryInterface
from app.schemas.entity import EntityCreate, EntityType
from app.schemas.relationship import RelationshipCreate, RelationshipType


class AIServiceInterface(ABC):
    """Abstract interface contract for AI/NLP document processing service."""

    @abstractmethod
    async def process_document(self, document_id: str, case_id: str, file_path: str) -> bool:
        """Trigger AI entity & relationship extraction pipeline."""
        pass

    @abstractmethod
    async def get_processing_status(self, document_id: str) -> DocumentProcessingStatusResponse:
        """Fetch current processing status of a document."""
        pass


class MockAIService(AIServiceInterface):
    """
    Mock implementation of AI/NLP service.
    Simulates asynchronous entity & relationship extraction so the backend functions
    end-to-end until the AI teammate connects their real NLP pipeline.
    """

    def __init__(
        self,
        doc_repo: DocumentRepositoryInterface = document_repository,
        ent_repo: EntityRepositoryInterface = entity_repository,
        rel_repo: RelationshipRepositoryInterface = relationship_repository,
        c_repo: CaseRepositoryInterface = case_repository,
    ):
        self._doc_repo = doc_repo
        self._ent_repo = ent_repo
        self._rel_repo = rel_repo
        self._case_repo = c_repo
        self._tasks: Dict[str, asyncio.Task] = {}

    async def process_document(self, document_id: str, case_id: str, file_path: str) -> bool:
        doc = await self._doc_repo.get_by_id(document_id)
        if not doc:
            return False

        # Set status to PROCESSING
        await self._doc_repo.update_status(document_id, ProcessingStatus.PROCESSING)

        # Run extraction task asynchronously in background
        task = asyncio.create_task(self._simulate_extraction(document_id, case_id))
        self._tasks[document_id] = task
        return True

    async def _simulate_extraction(self, document_id: str, case_id: str):
        try:
            await asyncio.sleep(0.5)  # Simulate model latency

            # Create sample extracted entities from evidence text
            suspect = await self._ent_repo.create(
                case_id=case_id,
                entity_create=EntityCreate(
                    name="Vikramaditya Sharma",
                    entity_type=EntityType.PERSON,
                    description="Primary suspect in financial fraud ring",
                    properties={"role": "Ring Leader", "alias": "Vicky"},
                    confidence_score=0.95,
                    source_document_id=document_id,
                ),
            )

            org = await self._ent_repo.create(
                case_id=case_id,
                entity_create=EntityCreate(
                    name="Apex Global Holdings LLC",
                    entity_type=EntityType.ORGANIZATION,
                    description="Shell company used for money laundering",
                    properties={"jurisdiction": "Offshore", "reg_number": "SH-990812"},
                    confidence_score=0.92,
                    source_document_id=document_id,
                ),
            )

            phone = await self._ent_repo.create(
                case_id=case_id,
                entity_create=EntityCreate(
                    name="+91-9876543210",
                    entity_type=EntityType.PHONE_NUMBER,
                    description="Encrypted phone used for wire instructions",
                    confidence_score=0.99,
                    source_document_id=document_id,
                ),
            )

            bank = await self._ent_repo.create(
                case_id=case_id,
                entity_create=EntityCreate(
                    name="ACC-8890-1120-4491",
                    entity_type=EntityType.BANK_ACCOUNT,
                    description="Swiss bank account receiving illicit transfers",
                    confidence_score=0.94,
                    source_document_id=document_id,
                ),
            )

            # Create relationships
            rel1 = await self._rel_repo.create(
                case_id=case_id,
                rel_create=RelationshipCreate(
                    source_entity_id=suspect.id,
                    target_entity_id=org.id,
                    relationship_type=RelationshipType.OWNER_OF,
                    description="Beneficial owner of shell company",
                    confidence_score=0.91,
                    source_document_id=document_id,
                ),
            )

            rel2 = await self._rel_repo.create(
                case_id=case_id,
                rel_create=RelationshipCreate(
                    source_entity_id=org.id,
                    target_entity_id=bank.id,
                    relationship_type=RelationshipType.TRANSFERRED_FUNDS,
                    description="Transferred $450,000 USD via wire",
                    confidence_score=0.88,
                    source_document_id=document_id,
                ),
            )

            rel3 = await self._rel_repo.create(
                case_id=case_id,
                rel_create=RelationshipCreate(
                    source_entity_id=suspect.id,
                    target_entity_id=phone.id,
                    relationship_type=RelationshipType.ASSOCIATED_WITH,
                    description="Registered phone line",
                    confidence_score=0.98,
                    source_document_id=document_id,
                ),
            )

            # Update document stats and status
            await self._doc_repo.update_extraction_counts(document_id, entity_count=4, relationship_count=3)
            await self._doc_repo.update_status(document_id, ProcessingStatus.COMPLETED)
            await self._case_repo.update_counts(case_id, entity_delta=4, rel_delta=3)

        except Exception as e:
            await self._doc_repo.update_status(document_id, ProcessingStatus.FAILED, error_message=str(e))

    async def get_processing_status(self, document_id: str) -> DocumentProcessingStatusResponse:
        doc = await self._doc_repo.get_by_id(document_id)
        if not doc:
            return DocumentProcessingStatusResponse(
                document_id=document_id,
                case_id="",
                processing_status=ProcessingStatus.FAILED,
                progress_percentage=0.0,
                message="Document not found",
            )

        progress = 100.0 if doc.processing_status == ProcessingStatus.COMPLETED else (50.0 if doc.processing_status == ProcessingStatus.PROCESSING else 0.0)
        return DocumentProcessingStatusResponse(
            document_id=doc.id,
            case_id=doc.case_id,
            processing_status=doc.processing_status,
            progress_percentage=progress,
            extracted_entity_count=doc.extracted_entity_count,
            extracted_relationship_count=doc.extracted_relationship_count,
            message=f"Document status is {doc.processing_status.value}",
        )


ai_service_integration = MockAIService()
