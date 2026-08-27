from typing import Any
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.security import create_access_token, verify_password
from app.schemas.user import UserResponse, UserCreate, Token
from app.schemas.auth import LoginRequest, RegisterRequest
from app.repositories.user_repo import UserRepositoryInterface
from app.api.deps import get_user_repository, get_current_user

router = APIRouter()


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED, summary="User Registration")
async def register_user(
    request: RegisterRequest,
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> Any:
    """Register a new user account."""
    existing_user = await user_repo.get_by_email(request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A user with this email address already exists.",
        )

    user_create = UserCreate(
        email=request.email,
        password=request.password,
        full_name=request.full_name,
        badge_number=request.badge_number,
        agency=request.agency,
    )
    user = await user_repo.create(user_create)
    return user


@router.post("/login", response_model=Token, summary="User Authentication & JWT Issuance (JSON)")
async def login_json(
    request: LoginRequest,
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> Any:
    """
    Authenticate user credentials via JSON request body.
    Returns access token and user profile.
    """
    user = await user_repo.get_by_email(request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    pwd_hash = await user_repo.get_password_hash(request.email)
    if not pwd_hash or not verify_password(request.password, pwd_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "email": user.email},
    )

    return Token(access_token=access_token, token_type="bearer", user=user)


@router.post("/login/form", response_model=Token, summary="OAuth2 Form Login (for Swagger UI / Form submit)")
async def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    user_repo: UserRepositoryInterface = Depends(get_user_repository),
) -> Any:
    """OAuth2 password flow form login endpoint."""
    user = await user_repo.get_by_email(form_data.username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    pwd_hash = await user_repo.get_password_hash(form_data.username)
    if not pwd_hash or not verify_password(form_data.password, pwd_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        subject=user.id,
        extra_claims={"role": user.role, "email": user.email},
    )

    return Token(access_token=access_token, token_type="bearer", user=user)


@router.get("/me", response_model=UserResponse, summary="Fetch Current User Profile")
async def read_current_user(
    current_user: UserResponse = Depends(get_current_user),
) -> Any:
    """Retrieve profile details for the currently authenticated user."""
    return current_user
