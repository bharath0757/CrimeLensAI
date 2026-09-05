"""One repository bundle shared by HTTP handlers and service integrations."""

from app.core.config import settings

if settings.DATA_BACKEND == "postgres":
    from app.repositories.postgres import (
        PostgresCaseRepository,
        PostgresDocumentRepository,
        PostgresEntityRepository,
        PostgresRelationshipRepository,
        PostgresUserRepository,
    )

    user_repository = PostgresUserRepository()
    case_repository = PostgresCaseRepository()
    document_repository = PostgresDocumentRepository()
    entity_repository = PostgresEntityRepository()
    relationship_repository = PostgresRelationshipRepository()
elif settings.DATA_BACKEND == "memory":
    from app.repositories.case_repo import case_repository
    from app.repositories.document_repo import document_repository
    from app.repositories.entity_repo import entity_repository
    from app.repositories.relationship_repo import relationship_repository
    from app.repositories.user_repo import user_repository
else:
    raise RuntimeError("DATA_BACKEND must be 'postgres' or 'memory'")

__all__ = [
    "case_repository",
    "document_repository",
    "entity_repository",
    "relationship_repository",
    "user_repository",
]
