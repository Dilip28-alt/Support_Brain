"""
Pydantic schemas for Auth and Business.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional
from uuid import UUID
from datetime import datetime
import re


# ─────── Business ───────

class BusinessCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None

    @validator("name")
    def name_valid(cls, v):
        if not v.strip():
            raise ValueError("Business name cannot be blank")
        return v.strip()


class BusinessResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    widget_token: Optional[str] = None
    description: Optional[str] = None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ─────── User / Auth ───────

class UserRegister(BaseModel):
    business_name: str = Field(..., min_length=2, max_length=255)
    business_description: Optional[str] = None
    full_name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8)

    @validator("password")
    def password_strength(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if len(v.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 bytes")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    business_id: UUID
    business_slug: str
    widget_token: Optional[str] = None
    user_id: UUID
    full_name: Optional[str] = None


class UserResponse(BaseModel):
    id: UUID
    business_id: UUID
    business_name: Optional[str] = None
    business_slug: Optional[str] = None
    widget_token: Optional[str] = None
    email: str
    full_name: Optional[str] = None
    is_owner: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True
