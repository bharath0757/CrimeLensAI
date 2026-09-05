"""Administrator-provisioned accounts and one credential-verification path."""

import asyncio
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import get_current_user, get_user_repository, require_roles
from app.core.security import create_access_token, get_password_hash, verify_password
from app.repositories.user_repo import UserRepositoryInterface
from app.schemas.auth import LoginRequest, RegisterRequest
from app.schemas.user import Token, UserCreate, UserResponse, UserRole

router = APIRouter()
Users = Annotated[UserRepositoryInterface, Depends(get_user_repository)]
Admin = Annotated[UserResponse, Depends(require_roles([UserRole.ADMIN]))]
# A missing account still performs a bcrypt check; never use this as an account hash.
DUMMY_PASSWORD_HASH = get_password_hash("non-account-timing-check-only")


@router.post("/register", response_model=UserResponse, status_code=201, summary="Provision officer account (Admin)")
async def register_user(request: RegisterRequest, current_user: Admin, user_repo: Users) -> UserResponse:
    if await user_repo.get_by_email(request.email):
        raise HTTPException(status_code=409, detail="A user with this email address already exists.")
    return await user_repo.create(UserCreate(**request.model_dump()))


async def authenticate(email: str, password: str, user_repo: UserRepositoryInterface) -> Token:
    user = await user_repo.get_by_email(email)
    password_hash = await user_repo.get_password_hash(email) if user else None
    valid = await asyncio.to_thread(verify_password, password, password_hash or DUMMY_PASSWORD_HASH)
    if not valid or not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Incorrect email or password.", headers={"WWW-Authenticate": "Bearer"})
    access_token = create_access_token(subject=user.id, extra_claims={"role": user.role, "email": user.email})
    return Token(access_token=access_token, token_type="bearer", user=user)


@router.post("/login", response_model=Token, summary="Officer login (JSON)")
async def login_json(request: LoginRequest, user_repo: Users) -> Token:
    return await authenticate(request.email, request.password, user_repo)


@router.post("/login/form", response_model=Token, summary="Officer login (OAuth2 form)")
async def login_form(form_data: Annotated[OAuth2PasswordRequestForm, Depends()], user_repo: Users) -> Token:
    return await authenticate(form_data.username, form_data.password, user_repo)


@router.get("/me", response_model=UserResponse, summary="Current officer profile")
async def read_current_user(current_user: Annotated[UserResponse, Depends(get_current_user)]) -> UserResponse:
    return current_user
