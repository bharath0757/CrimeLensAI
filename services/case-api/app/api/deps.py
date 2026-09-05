import hmac
from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from jwt import InvalidTokenError

from app.core.audit_context import audit_actor
from app.core.config import settings
from app.core.exceptions import CrimeLensException
from app.core.security import decode_access_token
from app.integrations.ai_integration import AIServiceInterface, ai_service_integration
from app.integrations.graph_integration import (
    GraphServiceInterface,
    graph_service_integration,
)
from app.repositories.case_repo import CaseRepositoryInterface
from app.repositories.document_repo import DocumentRepositoryInterface
from app.repositories.entity_repo import EntityRepositoryInterface
from app.repositories.registry import (
    case_repository,
    document_repository,
    entity_repository,
    relationship_repository,
    user_repository,
)
from app.repositories.relationship_repo import RelationshipRepositoryInterface
from app.repositories.user_repo import UserRepositoryInterface
from app.schemas.user import UserResponse, UserRole

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login/form")
service_key = APIKeyHeader(name="X-Service-Token", auto_error=False)


# Repository and Service Providers
def get_user_repository() -> UserRepositoryInterface:
    return user_repository


def get_case_repository() -> CaseRepositoryInterface:
    return case_repository


def get_document_repository() -> DocumentRepositoryInterface:
    return document_repository


def get_entity_repository() -> EntityRepositoryInterface:
    return entity_repository


def get_relationship_repository() -> RelationshipRepositoryInterface:
    return relationship_repository


def get_ai_service() -> AIServiceInterface:
    return ai_service_integration


def get_graph_service() -> GraphServiceInterface:
    return graph_service_integration


# Authentication and Authorization Dependencies
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: Annotated[UserRepositoryInterface, Depends(get_user_repository)],
) -> UserResponse:
    try:
        payload = decode_access_token(token)
        user_id: str | None = payload.get("sub")
        if user_id is None:
            raise CrimeLensException(message="Could not validate credentials", status_code=401)
    except (InvalidTokenError, CrimeLensException) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await user_repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Authentication session is no longer valid", headers={"WWW-Authenticate": "Bearer"})
    
    audit_actor.set(user.id)
    return user


def require_roles(allowed_roles: list[UserRole]) -> Callable:
    """Dependency for Role-Based Access Control (RBAC)."""
    async def role_checker(current_user: Annotated[UserResponse, Depends(get_current_user)]) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker


async def require_service_token(
    token: Annotated[str | None, Depends(service_key)],
) -> None:
    expected = settings.SERVICE_AUTH_TOKEN
    if len(expected.encode()) < 32:
        raise HTTPException(status_code=503, detail="Internal service authentication is not configured")
    if not token or not hmac.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="Invalid service credentials")
