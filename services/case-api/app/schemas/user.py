from enum import Enum
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserRole(str, Enum):
    ADMIN = "ADMIN"
    LEAD_INVESTIGATOR = "LEAD_INVESTIGATOR"
    ANALYST = "ANALYST"
    INVESTIGATOR = "INVESTIGATOR"


class UserBase(BaseModel):
    email: EmailStr
    full_name: str = Field(..., min_length=2, max_length=100)
    role: UserRole = UserRole.INVESTIGATOR
    badge_number: Optional[str] = None
    agency: Optional[str] = "CrimeLens AI Law Enforcement Agency"


class UserCreate(UserBase):
    password: str = Field(..., min_length=6, max_length=100)


class UserUpdate(BaseModel):
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    badge_number: Optional[str] = None
    agency: Optional[str] = None
    is_active: Optional[bool] = None


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
    sub: Optional[str] = None
    role: Optional[str] = None
