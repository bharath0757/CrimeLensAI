from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.schemas.user import UserCreate


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=1024)


class RegisterRequest(UserCreate):
    role: Literal["ADMIN", "INVESTIGATOR", "ANALYST"] = "INVESTIGATOR"
