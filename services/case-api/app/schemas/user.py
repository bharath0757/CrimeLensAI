from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserRole(StrEnum):
    ADMIN = "ADMIN"
    ANALYST = "ANALYST"
    INVESTIGATOR = "INVESTIGATOR"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.INVESTIGATOR
    badge_number: str | None = None
    agency: str | None = "CrimeLens AI Law Enforcement Agency"


class UserCreate(UserBase):
    password: str = Field(..., min_length=12, max_length=72)

    @field_validator("password")
    @classmethod
    def bcrypt_byte_limit(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must not exceed 72 UTF-8 bytes")
        return value


class UserUpdate(BaseModel):
    full_name: str | None = None
    role: UserRole | None = None
    badge_number: str | None = None
    agency: str | None = None
    is_active: bool | None = None


class UserResponse(UserBase):
    id: str
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class TokenPayload(BaseModel):
    sub: str | None = None
    role: str | None = None
