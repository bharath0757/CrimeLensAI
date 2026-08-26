from typing import List, Callable, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
import jwt

from app.core.config import settings
from app.core.exceptions import CrimeLensException
from app.core.security import decode_access_token
from app.schemas.user import UserResponse, UserRole
from app.repositories.user_repo import user_repository, UserRepositoryInterface
from app.repositories.case_repo import case_repository, CaseRepositoryInterface
from app.repositories.document_repo import document_repository, DocumentRepositoryInterface
from app.repositories.entity_repo import entity_repository, EntityRepositoryInterface
from app.repositories.relationship_repo import relationship_repository, RelationshipRepositoryInterface
from app.integrations.ai_integration import ai_service_integration, AIServiceInterface
from app.integrations.graph_integration import graph_service_integration, GraphServiceInterface

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")


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
    token: str = Depends(oauth2_scheme),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> UserResponse:
    try:
        payload = decode_access_token(token)
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise CrimeLensException(message="Could not validate credentials", status_code=401)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await user_repo.get_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inactive user account")
    
    return user


def require_roles(allowed_roles: List[UserRole]) -> Callable:
    """Dependency for Role-Based Access Control (RBAC)."""
    async def role_checker(current_user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{current_user.role}'. Required roles: {[r.value for r in allowed_roles]}",
            )
        return current_user
    return role_checker
