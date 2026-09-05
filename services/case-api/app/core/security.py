from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import CrimeLensException


def get_password_hash(password: str) -> str:
    """Hash password using bcrypt."""
    pwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against hashed password."""
    try:
        plain_bytes = plain_password.encode('utf-8')
        hashed_bytes = hashed_password.encode('utf-8')
        return bcrypt.checkpw(plain_bytes, hashed_bytes)
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None, extra_claims: dict[str, Any] | None = None) -> str:
    """Create signed JWT access token."""
    if expires_delta is not None:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "iat": datetime.now(UTC),
        "iss": settings.JWT_ISSUER,
        "aud": settings.JWT_AUDIENCE,
        "jti": str(uuid4()),
    }
    if extra_claims:
        if set(extra_claims) & set(to_encode):
            raise ValueError("Extra claims cannot override registered token claims")
        to_encode.update(extra_claims)
        
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate JWT access token."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM],
                          issuer=settings.JWT_ISSUER, audience=settings.JWT_AUDIENCE,
                          options={"require": ["exp", "iat", "sub", "iss", "aud", "jti"]})
    except jwt.ExpiredSignatureError as exc:
        raise CrimeLensException(message="Authentication token has expired.", status_code=401) from exc
    except jwt.InvalidTokenError as exc:
        raise CrimeLensException(message="Invalid authentication token.", status_code=401) from exc
