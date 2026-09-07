from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.schemas.user import UserCreate


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("email", "password", mode="before")
    @classmethod
    def strip_whitespace(cls, v: Any) -> Any:
        if isinstance(v, str):
            return v.strip()
        return v


class RegisterRequest(UserCreate):
    role: Literal["ADMIN", "INVESTIGATOR", "ANALYST"] = "INVESTIGATOR"
